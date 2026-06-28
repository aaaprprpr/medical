from __future__ import absolute_import, division, print_function
import logging
import argparse
import torch
from tqdm import tqdm
from torch.utils.tensorboard import SummaryWriter
try:
    from torch.amp import autocast, GradScaler
    _TORCH_AMP_NEW_API = True
except ImportError:
    from torch.cuda.amp import autocast, GradScaler
    _TORCH_AMP_NEW_API = False
from models.modeling import CONFIGS, DSFI
from util.scheduler import WarmupLinearSchedule, WarmupCosineSchedule
from util.data_utils import get_loader
from models.IEPV import IEPV
from models import vit
from settings.defaults import _C
from settings.setup_functions import *
import time
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
import numpy as np

backbone = {
	'ViT-B_16': vit.get_b16_config()
}


logger = logging.getLogger(__name__)


def autocast_cuda(enabled):
    if _TORCH_AMP_NEW_API:
        return autocast("cuda", enabled=enabled)
    return autocast(enabled=enabled)


def create_grad_scaler(enabled):
    if _TORCH_AMP_NEW_API:
        return GradScaler("cuda", enabled=enabled)
    return GradScaler(enabled=enabled)


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def simple_accuracy(preds, labels):
    return (preds == labels).mean()


def save_model(args, model):
    model_to_save = model.module if hasattr(model, 'module') else model
    model_checkpoint = os.path.join(args.output_dir, "%s_checkpoint.pth" % args.name)
    torch.save({'model': model_to_save.state_dict()}, model_checkpoint)
    logger.info("Saved model checkpoint to [DIR: %s]", args.output_dir)

def setup_img(args):
    config = _C.clone()
    cfg_file = os.path.join('configs', 'MACE.yaml')
    config = SetupConfig(config, cfg_file)
    config.defrost()
    ## Log Name and Perferences
    config.write = True  # comment it to disable all the log writing
    config.train.checkpoint = True  # comment it to disable saving the checkpoint
    config.misc.exp_name = f'{config.data.dataset}'
    config.misc.log_name = f'IELT'
    config.cuda_visible = '0,1,2,3'
    # Environment Settings
    config.data.log_path = os.path.join(config.misc.output, config.misc.exp_name, config.misc.log_name
                                        + time.strftime('-%m-%d_%H-%M', time.localtime()))

    config.model.pretrained = os.path.join(config.model.pretrained,
                                           config.model.name + config.model.pre_version + config.model.pre_suffix)
    os.environ['CUDA_VISIBLE_DEVICES'] = config.cuda_visible
    os.environ['OMP_NUM_THREADS'] = '1'
    # Setup Functions
    config.nprocess, config.local_rank = SetupDevice()
    config.data.data_root, config.data.batch_size = LocateDatasets(config)
    config.train.lr = ScaleLr(config)
    log = SetupLogs(config, config.local_rank)
    if config.write and config.local_rank in [-1, 0]:
        with open(config.data.log_path + '/config.json', "w") as f:
            f.write(config.dump())
    config.freeze()
    SetSeed(config)
    num_classes = 2
    structure = vit.get_b16_config()
    args.use_mask = bool(config.parameters.use_mask)
    model = IEPV(structure, config.data.img_size, num_classes, use_mask=args.use_mask)
    model.to(args.device)
    return args, model, structure




def model_sequence_setup(args, structure):
    sequence_config = CONFIGS['sequence']
    model = DSFI(sequence_config, structure, num_classes=2, zero_head=True, vis=True)
    model.to(args.device)
    return model




def set_seed(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)


def sequence_class_weights(dataset, device):
    labels = []
    for target_type in dataset.target_dic.values():
        labels.append(1 if target_type == 'mace_cine' else 0)
    counts = np.bincount(labels, minlength=2).astype(np.float32)
    counts[counts == 0] = 1.0
    weights = counts.sum() / (len(counts) * counts)
    return torch.tensor(weights, dtype=torch.float32, device=device), counts


def extract_image_features(args, model_img, model_img_LGE, x, lge_images, mask=None, lge_masks=None):
    batch_size, sequence_length = x.shape[:2]
    x_flat = x.reshape(batch_size * sequence_length, *x.shape[2:])
    mask_flat = mask.reshape(batch_size * sequence_length, *mask.shape[2:]) if args.use_mask else None
    _, cine_feature = model_img(x_flat, mask=mask_flat, test_mode=True)
    cine_feature = cine_feature.reshape(batch_size, sequence_length, *cine_feature.shape[1:])

    lge_length = lge_images.shape[1]
    lge_flat = lge_images.reshape(batch_size * lge_length, *lge_images.shape[2:])
    lge_mask_flat = lge_masks.reshape(batch_size * lge_length, *lge_masks.shape[2:]) if args.use_mask else None
    _, lge_feature = model_img_LGE(lge_flat, mask=lge_mask_flat, test_mode=True)
    lge_feature = lge_feature.reshape(batch_size, lge_length, *lge_feature.shape[1:])

    missing_lge = lge_images.reshape(batch_size, -1).abs().sum(dim=1) == 0
    if missing_lge.any():
        lge_feature = lge_feature.clone()
        lge_feature[missing_lge] = 0

    return cine_feature, lge_feature



def valid(args, model_img, model_img_LGE, model, writer, test_loader, global_step):
    # Validation!
    eval_losses = AverageMeter()
    logger.info("***** Running Validation *****")
    logger.info("  Num steps = %d", len(test_loader))
    logger.info("  Batch size = %d", args.eval_batch_size)
    model_img.eval()
    model_img_LGE.eval()
    model.eval()
    all_preds, all_label, all_logits = [], [], []
    epoch_iterator = tqdm(test_loader,
                          desc="Validating... (loss=X.X)",
                          bar_format="{l_bar}{r_bar}",
                          dynamic_ncols=True,
                          disable=False)
    loss_fct = torch.nn.CrossEntropyLoss()
    for step, batch in enumerate(epoch_iterator):
        torch.cuda.empty_cache()
        model_img.eval()
        model_img_LGE.eval()
        model.eval()
        batch = tuple(t.to(args.device) for t in batch)
        if args.use_mask:
            x, mask, LGE_images, LGE_masks, y = batch
        else:
            x, LGE_images, y = batch
        with torch.no_grad():
            Cine_feature, LGE_feature = extract_image_features(
                args,
                model_img,
                model_img_LGE,
                x,
                LGE_images,
                mask=mask if args.use_mask else None,
                lge_masks=LGE_masks if args.use_mask else None,
            )
            logits = model(Cine_feature, LGE_feature)[0]

            eval_loss = loss_fct(logits, y)
            eval_losses.update(eval_loss.item())

            preds = torch.argmax(logits, dim=-1)


        if len(all_preds) == 0:
            all_preds.append(preds.detach().cpu().numpy())
            all_label.append(y.detach().cpu().numpy())
            all_logits.append(logits.detach().cpu().numpy())
        else:
            all_preds[0] = np.append(
                all_preds[0], preds.detach().cpu().numpy(), axis=0
            )
            all_label[0] = np.append(
                all_label[0], y.detach().cpu().numpy(), axis=0
            )
            all_logits[0] = np.append(
                all_logits[0], logits.detach().cpu().numpy(), axis=0
            )
        epoch_iterator.set_description("Validating... (loss=%2.5f)" % eval_losses.val)

    all_preds, all_label, all_logits = all_preds[0], all_label[0], all_logits[0]
    accuracy = simple_accuracy(all_preds, all_label)
    all_probs = torch.softmax(torch.from_numpy(all_logits), dim=1).numpy()[:, 1]
    auc = roc_auc_score(all_label, all_probs)
    ap = average_precision_score(all_label, all_probs)
    balanced_acc = balanced_accuracy_score(all_label, all_preds)
    f1 = f1_score(all_label, all_preds, zero_division=0)
    selection_score = balanced_acc + 0.25 * f1 - eval_losses.avg
    logger.info("\n")
    logger.info("Validation Results")
    logger.info("Global Steps: %d" % global_step)
    logger.info("Valid Loss: %2.5f" % eval_losses.avg)
    logger.info("Valid Accuracy: %2.5f" % accuracy)
    logger.info("Valid Balanced Accuracy: %2.5f" % balanced_acc)
    logger.info("Valid F1: %2.5f" % f1)
    logger.info("Valid AUC: %2.5f" % auc)
    logger.info("Valid AP: %2.5f" % ap)
    logger.info("Valid Selection Score: %2.5f" % selection_score)

    writer.add_scalar("test/accuracy", scalar_value=accuracy, global_step=global_step)
    writer.add_scalar("test/balanced_accuracy", scalar_value=balanced_acc, global_step=global_step)
    writer.add_scalar("test/f1", scalar_value=f1, global_step=global_step)
    writer.add_scalar("test/AUC", scalar_value=auc, global_step=global_step)
    writer.add_scalar("test/AP", scalar_value=ap, global_step=global_step)
    writer.add_scalar("test/loss", scalar_value=eval_losses.avg, global_step=global_step)
    writer.add_scalar("test/selection_score", scalar_value=selection_score, global_step=global_step)
    return {
        "loss": eval_losses.avg,
        "accuracy": accuracy,
        "balanced_accuracy": balanced_acc,
        "f1": f1,
        "auc": auc,
        "ap": ap,
        "selection_score": selection_score,
    }


def train(args, model_img,model_img_LGE, model):
    for p in model_img.parameters():
        p.requires_grad = False
    for p in model_img_LGE.parameters():
        p.requires_grad = False

    model_img.eval()
    model_img_LGE.eval()
    model.train()
    """ Train the model """

    os.makedirs(args.output_dir, exist_ok=True)
    writer = SummaryWriter(log_dir=os.path.join("logs", args.name))

    args.train_batch_size = args.train_batch_size // args.gradient_accumulation_steps

    # Prepare dataset
    train_loader, test_loader = get_loader(args)
    class_weights, class_counts = sequence_class_weights(train_loader.dataset, args.device)
    logger.info("  Sequence class counts = %s", class_counts.astype(int).tolist())
    logger.info("  Sequence class weights = %s", [round(v, 6) for v in class_weights.detach().cpu().tolist()])

    optimizer = torch.optim.Adam(model.parameters(),
                                lr=args.learning_rate,
                                weight_decay=args.weight_decay)
    t_total = args.num_steps
    if args.decay_type == "cosine":
        scheduler = WarmupCosineSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)
    else:
        scheduler = WarmupLinearSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)

    amp_enabled = bool(args.fp16 and args.device.type == "cuda")
    scaler = create_grad_scaler(amp_enabled)


    # Train!
    logger.info("***** Running training *****")
    logger.info("  Total optimization steps = %d", args.num_steps)
    logger.info("  Instantaneous batch size per GPU = %d", args.train_batch_size)
    logger.info("  Total train batch size (w. parallel, distributed & accumulation) = %d",
                args.train_batch_size * args.gradient_accumulation_steps)
    logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)

    model.zero_grad()
    set_seed(args)  # Added here for reproducibility (even between python 2 and 3)
    losses = AverageMeter()
    global_step, best_score = 0, -float("inf")
    while True:
        epoch_iterator = tqdm(train_loader,
                              desc="Training (X / X Steps) (loss=X.X)",
                              bar_format="{l_bar}{r_bar}",
                              dynamic_ncols=True,
                              disable=False)
        for step, batch in enumerate(epoch_iterator):
            torch.cuda.empty_cache()
            model_img.eval()
            model_img_LGE.eval()
            model.train()
            batch = tuple(t.to(args.device) for t in batch)
            if args.use_mask:
                x, mask, LGE_images, LGE_masks, y = batch
            else:
                x, LGE_images, y = batch
            with torch.no_grad():
                Cine_feature, LGE_feature = extract_image_features(
                    args,
                    model_img,
                    model_img_LGE,
                    x,
                    LGE_images,
                    mask=mask if args.use_mask else None,
                    lge_masks=LGE_masks if args.use_mask else None,
                )

            with autocast_cuda(amp_enabled):
                loss = model(Cine_feature, LGE_feature, y, class_weights=class_weights)

            if args.gradient_accumulation_steps > 1:
                loss = loss / args.gradient_accumulation_steps
            if amp_enabled:
                scaler.scale(loss).backward()
            else:
                loss.backward()

            if (step + 1) % args.gradient_accumulation_steps == 0:
                losses.update(loss.item()*args.gradient_accumulation_steps)
                if amp_enabled:
                    scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                if amp_enabled:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                epoch_iterator.set_description(
                    "Training (%d / %d Steps) (loss=%2.5f)" % (global_step, t_total, losses.val)
                )
                writer.add_scalar("train/loss", scalar_value=losses.val, global_step=global_step)
                writer.add_scalar("train/lr", scalar_value=scheduler.get_last_lr()[0], global_step=global_step)

                if global_step % args.eval_every == 0 :
                    torch.cuda.empty_cache()
                    with torch.no_grad():
                        metrics = valid(args, model_img, model_img_LGE, model, writer, test_loader, global_step)
                    if metrics["selection_score"] > best_score:
                        save_model(args, model)
                        best_score = metrics["selection_score"]
                    model.train()

                if global_step % t_total == 0:
                    break
        losses.reset()
        if global_step % t_total == 0:
            break


    writer.close()
    logger.info("Best selection score: \t%f" % best_score)
    logger.info("End Training!")


def main():
    parser = argparse.ArgumentParser()
    # Required parameters
    parser.add_argument("--name", type=str, default="TTST_SequenceTraining",
                        help="Name of this run. Used for monitoring.")
    parser.add_argument("--dataset", type=str, default="MACE")
    parser.add_argument("--model_img_checkpoints_dir", type=str, nargs='+',
                        default=[r"output\Cine_img_model_checkpoint.pth", r"output\LGE_img_model_checkpoint.pth"],
                        help='List of model image checkpoint files')
    parser.add_argument("--resume_sequence_checkpoint", type=str, default=None,
                        help="Optional DSFI sequence checkpoint to load before training.")

    parser.add_argument("--train_data_folder", type=str, default=r"Dataset\train")
    parser.add_argument("--test_data_folder", type=str,  default=r"Dataset\test")

    parser.add_argument("--model_type", type=str ,default="ViT-B_16")
    parser.add_argument("--output_dir", default="output", type=str,
                        help="The output directory where checkpoints will be written.")

    parser.add_argument("--img_size", default=224, type=int,
                        help="Resolution size")
    parser.add_argument("--train_batch_size", default=2, type=int,
                        help="Total batch size for training.")
    parser.add_argument("--eval_batch_size", default=1, type=int,
                        help="Total batch size for eval.")
    parser.add_argument("--eval_every", default=25, type=int)
    parser.add_argument("--learning_rate", default=3e-5, type=float,
                        help="The initial learning rate.")
    parser.add_argument("--weight_decay", default=1e-4, type=float,
                        help="Weight deay if we apply some.")
    parser.add_argument("--num_steps", default=800, type=int,
                        help="Total number of training epochs to perform.")
    parser.add_argument("--decay_type", choices=["cosine", "linear"], default="cosine",
                        help="How to decay the learning rate.")
    parser.add_argument("--warmup_steps", default=50, type=int,
                        help="Step of training to perform learning rate warmup for.")
    parser.add_argument("--max_grad_norm", default=1.0, type=float,
                        help="Max gradient norm.")
    parser.add_argument('--seed', type=int, default=0,
                        help="random seed for initialization")
    parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
                        help="Number of updates steps to accumulate before performing a backward/update pass.")
    parser.add_argument('--fp16', action='store_true',
                        help="Whether to use 16-bit float precision instead of 32-bit")
    parser.add_argument('--fp16_opt_level', type=str, default='O2',
                        help="Deprecated compatibility option. PyTorch AMP is used when --fp16 is set.")
    parser.add_argument('--loss_scale', type=float, default=0,
                        help="Loss scaling to improve fp16 numeric stability. Only used when fp16 set to True.\n"
                             "0 (default value): dynamic loss scaling.\n"
                             "Positive power of 2: static loss scaling value.\n")
    args = parser.parse_args()


    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.device = device

    # Setup logging
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=logging.INFO)
    logger.warning(" device: %s, 16-bits training: %s" %
                   ( args.device,  args.fp16))

    # Set seed
    set_seed(args)

    # Model & Tokenizer Setup
    args, model_img, structure = setup_img(args)
    state_dict = torch.load(args.model_img_checkpoints_dir[0])
    model_img.load_state_dict(state_dict['model'], strict=False)
    args, model_img_LGE, structure = setup_img(args)
    state_dict = torch.load(args.model_img_checkpoints_dir[1])
    model_img_LGE.load_state_dict(state_dict['model'], strict=False)

    model_sequence = model_sequence_setup(args, structure)
    if args.resume_sequence_checkpoint:
        logger.info("Loading sequence checkpoint from %s", args.resume_sequence_checkpoint)
        state_dict = torch.load(args.resume_sequence_checkpoint, map_location=args.device)
        model_sequence.load_state_dict(state_dict["model"], strict=False)

    # Training
    train(args, model_img, model_img_LGE, model_sequence)


if __name__ == "__main__":
    main()
