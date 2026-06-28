
from __future__ import absolute_import, division, print_function

import logging
import argparse
from datetime import timedelta
import torch
import torch.distributed as dist
from tqdm import tqdm
from torch.utils.tensorboard import SummaryWriter
try:
    from torch.amp import autocast, GradScaler
    _TORCH_AMP_NEW_API = True
except ImportError:
    from torch.cuda.amp import autocast, GradScaler
    _TORCH_AMP_NEW_API = False
from torch.nn.parallel import DistributedDataParallel as DDP
from util.scheduler import WarmupLinearSchedule, WarmupCosineSchedule
from util.data_utils import get_loader_img
from models.IEPV import IEPV
from models import vit
from settings.defaults import _C
from settings.setup_functions import *
import time
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
import numpy as np


backbone = {
	'ViT-B_16': vit.get_b16_config(),

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


def configure_finetuning(model, mode):
    if mode == "all":
        for param in model.parameters():
            param.requires_grad = True
    else:
        for param in model.parameters():
            param.requires_grad = False

        for param in model.head.parameters():
            param.requires_grad = True

        if mode in {"head_clr", "last", "last2"}:
            for param in model.encoder.clr_layer.parameters():
                param.requires_grad = True

        if mode in {"last", "last2"}:
            for param in model.encoder.layer[-1].parameters():
                param.requires_grad = True

        if mode == "last2":
            for param in model.encoder.layer[-2].parameters():
                param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def image_class_weights(dataset, device):
    targets = np.asarray(dataset.targets)
    counts = np.bincount(targets, minlength=len(dataset.classes)).astype(np.float32)
    counts[counts == 0] = 1.0
    weights = counts.sum() / (len(counts) * counts)
    return torch.tensor(weights, dtype=torch.float32, device=device), counts


def setup(args):
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
    structure = backbone[config.model.name]
    args.use_mask = bool(config.parameters.use_mask)
    model = IEPV(structure, config.data.img_size, num_classes, use_mask=args.use_mask)
    if os.path.exists(config.model.pretrained):
        logger.info("Loading ViT pretrained weights from %s", config.model.pretrained)
        model.load_from(config.model.pretrained)
    else:
        logger.warning("ViT pretrained weights not found: %s", config.model.pretrained)
    trainable, total = configure_finetuning(model, args.finetune_mode)
    logger.info("Finetune mode: %s (%d/%d trainable parameters)", args.finetune_mode, trainable, total)
    model.to(args.device)
    return args, model




def set_seed(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)



def valid(args, model, writer, test_loader, global_step):
    # Validation!
    eval_losses = AverageMeter()
    logger.info("***** Running Validation *****")
    logger.info("  Num steps = %d", len(test_loader))
    logger.info("  Batch size = %d", args.eval_batch_size)

    model.eval()
    all_preds, all_label, all_logits = [], [], []
    epoch_iterator = tqdm(test_loader,
                          desc="Validating... (loss=X.X)",
                          bar_format="{l_bar}{r_bar}",
                          dynamic_ncols=True,
                          disable=args.local_rank not in [-1, 0])
    loss_fct = torch.nn.CrossEntropyLoss()
    for step, batch in enumerate(epoch_iterator):
        batch = tuple(t.to(args.device) for t in batch)
        if args.use_mask:
            x, mask, y = batch
        else:
            x, y = batch

        with torch.no_grad():
            logits, _ = model(x, mask=mask if args.use_mask else None, labels=y, test_mode=True)

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

    all_preds, all_label, all_logits= all_preds[0], all_label[0], all_logits[0]
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


def train(args, model):
    """ Train the model """
    if args.local_rank in [-1, 0]:
        os.makedirs(args.output_dir, exist_ok=True)
        writer = SummaryWriter(log_dir=os.path.join("logs", args.name))

    args.train_batch_size = args.train_batch_size // args.gradient_accumulation_steps

    # Prepare dataset
    train_loader, test_loader = get_loader_img(args)
    class_weights = None
    if args.class_weighted_loss:
        class_weights, class_counts = image_class_weights(train_loader.dataset, args.device)
        logger.info("  Image class counts = %s", class_counts.astype(int).tolist())
        logger.info("  Image class weights = %s", [round(v, 6) for v in class_weights.detach().cpu().tolist()])

    # Prepare optimizer and scheduler
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(trainable_params,
                                lr=args.learning_rate,
                                momentum=0.9,
                                weight_decay=args.weight_decay)
    t_total = args.num_steps
    if args.decay_type == "cosine":
        scheduler = WarmupCosineSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)
    else:
        scheduler = WarmupLinearSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)

    amp_enabled = bool(args.fp16 and args.device.type == "cuda")
    scaler = create_grad_scaler(amp_enabled)

    # Distributed training
    if args.local_rank != -1:
        model = DDP(model, device_ids=[args.local_rank] if args.device.type == "cuda" else None)

    # Train!
    logger.info("***** Running training *****")
    logger.info("  Total optimization steps = %d", args.num_steps)
    logger.info("  Instantaneous batch size per GPU = %d", args.train_batch_size)
    logger.info("  Total train batch size (w. parallel, distributed & accumulation) = %d",
                args.train_batch_size * args.gradient_accumulation_steps * (
                    torch.distributed.get_world_size() if args.local_rank != -1 else 1))
    logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)

    model.zero_grad()
    set_seed(args)  # Added here for reproducibility (even between python 2 and 3)
    losses = AverageMeter()
    global_step, best_score = 0, -float("inf")
    while True:
        model.train()
        epoch_iterator = tqdm(train_loader,
                              desc="Training (X / X Steps) (loss=X.X)",
                              bar_format="{l_bar}{r_bar}",
                              dynamic_ncols=True,
                              disable=args.local_rank not in [-1, 0])
        for step, batch in enumerate(epoch_iterator):
            batch = tuple(t.to(args.device) for t in batch)
            if args.use_mask:
                x, mask, y = batch
            else:
                x, y = batch

            # loss = model(x, feature, y)
            with autocast_cuda(amp_enabled):
                if class_weights is None:
                    _, _, loss = model(x, mask=mask if args.use_mask else None, labels=y)
                else:
                    logits, _ = model(x, mask=mask if args.use_mask else None, test_mode=True)
                    loss = torch.nn.functional.cross_entropy(logits, y, weight=class_weights)

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
                torch.nn.utils.clip_grad_norm_(trainable_params, args.max_grad_norm)
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
                if args.local_rank in [-1, 0]:
                    writer.add_scalar("train/loss", scalar_value=losses.val, global_step=global_step)
                    writer.add_scalar("train/lr", scalar_value=scheduler.get_last_lr()[0], global_step=global_step)
                if global_step % args.eval_every == 0 and args.local_rank in [-1, 0]:
                    metrics = valid(args, model, writer, test_loader, global_step)
                    if metrics["selection_score"] > best_score:
                        save_model(args, model)
                        best_score = metrics["selection_score"]
                    model.train()

                if global_step % t_total == 0:
                    break
        losses.reset()
        if global_step % t_total == 0:
            break

    if args.local_rank in [-1, 0]:
        writer.close()
    logger.info("Best selection score: \t%f" % best_score)
    logger.info("End Training!")


def main():
    parser = argparse.ArgumentParser()
    # Required parameters
    parser.add_argument("--name", type=str, default="LGE_img_model",
                        help="Name of this run. Used for monitoring.")
    parser.add_argument("--dataset", type=str, default="MACE")

    parser.add_argument("--train_data_folder", type=str, default=r"Dataset\train_LGE")
    parser.add_argument("--test_data_folder", type=str, default=r"Dataset\test_LGE")
    parser.add_argument("--model_type", type=str ,default="ViT-B_16")
    parser.add_argument("--output_dir", default="output", type=str,
                        help="The output directory where checkpoints will be written.")

    parser.add_argument("--img_size", default=224, type=int,
                        help="Resolution size")
    parser.add_argument("--train_batch_size", default=32, type=int,
                        help="Total batch size for training.")
    parser.add_argument("--eval_batch_size", default=32, type=int,
                        help="Total batch size for eval.")
    parser.add_argument("--eval_every", default=10, type=int,
                        help="Run prediction on validation set every so many steps."
                             "Will always run one evaluation at the end of training.")

    parser.add_argument("--learning_rate", default=1e-4, type=float,
                        help="The initial learning rate for.")
    parser.add_argument("--weight_decay", default=1e-4, type=float,
                        help="Weight deay if we apply some.")
    parser.add_argument("--num_steps", default=500, type=int,
                        help="Total number of training epochs to perform.")
    parser.add_argument("--decay_type", choices=["cosine", "linear"], default="cosine",
                        help="How to decay the learning rate.")
    parser.add_argument("--finetune_mode", choices=["all", "head", "head_clr", "last", "last2"], default="all",
                        help="Which ViT parameters to train after loading pretrained weights.")
    parser.add_argument("--balanced_sampler", action="store_true",
                        help="Use class-balanced sampling for image-level training.")
    parser.add_argument("--class_weighted_loss", action="store_true",
                        help="Use inverse-frequency class weights in image-level cross entropy.")
    parser.add_argument("--warmup_steps", default=50, type=int,
                        help="Step of training to perform learning rate warmup for.")
    parser.add_argument("--max_grad_norm", default=1.0, type=float,
                        help="Max gradient norm.")

    parser.add_argument("--local_rank", type=int, default=-1,
                        help="local_rank for distributed training on gpus")
    parser.add_argument('--seed', type=int, default=42,
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
    args, model = setup(args)

    # Training
    train(args, model)


if __name__ == "__main__":
    main()
