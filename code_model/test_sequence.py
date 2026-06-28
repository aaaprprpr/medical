from __future__ import absolute_import, division, print_function
import os
import logging
import argparse
from tqdm import tqdm
import torch
import numpy as np
from sklearn.metrics import roc_auc_score

from models.modeling import CONFIGS, DSFI
from models.IEPV import IEPV
from models import vit
from util.data_utils import get_loader
from settings.defaults import _C
from settings.setup_functions import *

logger = logging.getLogger(__name__)

backbone = {
    'ViT-B_16': vit.get_b16_config()
}


class AverageMeter(object):
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


def setup_img(args):
    config = _C.clone()
    cfg_file = os.path.join('configs', 'MACE.yaml')
    config = SetupConfig(config, cfg_file)

    config.defrost()
    config.cuda_visible = '0'
    os.environ['CUDA_VISIBLE_DEVICES'] = config.cuda_visible

    config.nprocess, config.local_rank = SetupDevice()
    config.data.data_root, config.data.batch_size = LocateDatasets(config)

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

    model = DSFI(sequence_config,
                 structure,
                 num_classes=2,
                 zero_head=True,
                 vis=True)

    model.to(args.device)

    return model


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


def valid(args, model_img, model_img_LGE, model, test_loader):

    eval_losses = AverageMeter()

    model_img.eval()
    model_img_LGE.eval()
    model.eval()

    all_preds = []
    all_label = []
    all_logits = []

    loss_fct = torch.nn.CrossEntropyLoss()

    epoch_iterator = tqdm(
        test_loader,
        desc="Testing...",
        bar_format="{l_bar}{r_bar}",
        dynamic_ncols=True
    )

    for step, batch in enumerate(epoch_iterator):

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

            loss = loss_fct(logits, y)

            eval_losses.update(loss.item())

            preds = torch.argmax(logits, dim=-1)

        if len(all_preds) == 0:

            all_preds.append(preds.detach().cpu().numpy())
            all_label.append(y.detach().cpu().numpy())
            all_logits.append(logits.detach().cpu().numpy())

        else:

            all_preds[0] = np.append(
                all_preds[0],
                preds.detach().cpu().numpy(),
                axis=0
            )

            all_label[0] = np.append(
                all_label[0],
                y.detach().cpu().numpy(),
                axis=0
            )

            all_logits[0] = np.append(
                all_logits[0],
                logits.detach().cpu().numpy(),
                axis=0
            )

    all_preds, all_label, all_logits = all_preds[0], all_label[0], all_logits[0]

    accuracy = simple_accuracy(all_preds, all_label)

    all_probs = torch.softmax(torch.from_numpy(all_logits), dim=1).numpy()[:, 1]
    auc = roc_auc_score(all_label, all_probs)

    logger.info("Test Loss: %.5f", eval_losses.avg)
    logger.info("Test Accuracy: %.5f", accuracy)
    logger.info("Test AUC: %.5f", auc)

    print("\n========== Test Result ==========")
    print("Accuracy:", accuracy)
    print("AUC:", auc)
    print("=================================\n")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--dataset", default="MACE")

    parser.add_argument("--model_img_checkpoints_dir",
                        nargs='+',
                        default=[
                            "output/Cine_img_model_checkpoint.pth",
                            "output/LGE_img_model_checkpoint.pth"
                        ])

    parser.add_argument("--sequence_checkpoint",
                        default="output/TTST_SequenceTraining_checkpoint.pth")

    parser.add_argument("--train_data_folder",
                        default=r"Dataset\train")

    parser.add_argument("--test_data_folder",
                        default=r"Dataset\test")

    parser.add_argument("--eval_batch_size",
                        default=1,
                        type=int)
    parser.add_argument("--train_batch_size",
                        default=1,
                        type=int)

    parser.add_argument("--img_size",
                        default=224,
                        type=int)

    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.device = device

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        level=logging.INFO
    )

    logger.warning("device: %s", device)

    # image encoder
    args, model_img, structure = setup_img(args)

    state_dict = torch.load(args.model_img_checkpoints_dir[0])
    model_img.load_state_dict(state_dict['model'], strict=False)

    args, model_img_LGE, structure = setup_img(args)

    state_dict = torch.load(args.model_img_checkpoints_dir[1])
    model_img_LGE.load_state_dict(state_dict['model'], strict=False)

    # sequence model
    model_sequence = model_sequence_setup(args, structure)

    seq_ckpt = torch.load(args.sequence_checkpoint)
    model_sequence.load_state_dict(seq_ckpt['model'])

    # dataset
    _, test_loader = get_loader(args)

    # run test
    valid(args, model_img, model_img_LGE, model_sequence, test_loader)


if __name__ == "__main__":
    main()
