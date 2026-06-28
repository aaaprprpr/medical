import time
import torch

import numpy as np
from scipy import ndimage
from torch.nn import CrossEntropyLoss
import torch.nn.functional as F
from models.modules import *
from models.vit import get_b16_config


class IEPV(nn.Module):
	def __init__(self, config, img_size=224, num_classes=2,
	             vote_perhead=24, use_mask=None):
		super(IEPV, self).__init__()

		self.num_classes = num_classes
		if use_mask is not None:
			config.use_mask = use_mask
		self.use_mask = getattr(config, "use_mask", True)
		self.embeddings = Embeddings(config, img_size=img_size)
		self.encoder = IEPVEncoder(config,  vote_perhead)
		self.head = Linear(config.hidden_size, num_classes)
		self.softmax = Softmax(dim=-1)

	def load_from(self, weights_path):
		weights = np.load(weights_path)
		with torch.no_grad():
			self.embeddings.patch_embeddings.weight.copy_(np2th(weights["embedding/kernel"], conv=True))
			self.embeddings.patch_embeddings.bias.copy_(np2th(weights["embedding/bias"]))
			if hasattr(self.embeddings, "mask_patch_embeddings"):
				self.embeddings.mask_patch_embeddings.weight.copy_(self.embeddings.patch_embeddings.weight)
				self.embeddings.mask_patch_embeddings.bias.copy_(self.embeddings.patch_embeddings.bias)
			self.embeddings.cls_token.copy_(np2th(weights["cls"]))
			self.embeddings.position_embeddings.copy_(np2th(weights["Transformer/posembed_input/pos_embedding"]))

			for block_index, block in enumerate(self.encoder.layer):
				self._load_block(block, weights, block_index)
			self._load_block(self.encoder.clr_layer, weights, len(self.encoder.layer))

	def _load_block(self, block, weights, block_index):
		root = f"Transformer/encoderblock_{block_index}"
		def linear_weight(name):
			value = weights[name]
			value = value.reshape(value.shape[0], -1) if value.ndim == 3 and name.endswith("kernel") else value
			return np2th(value).t()

		def attention_out_weight(name):
			value = weights[name]
			value = value.reshape(-1, value.shape[-1]) if value.ndim == 3 else value
			return np2th(value).t()

		def attention_bias(name):
			value = weights[name]
			value = value.reshape(-1) if value.ndim > 1 else value
			return np2th(value)

		block.attention_norm.weight.copy_(np2th(weights[f"{root}/{ATTENTION_NORM}/scale"]))
		block.attention_norm.bias.copy_(np2th(weights[f"{root}/{ATTENTION_NORM}/bias"]))
		block.ffn_norm.weight.copy_(np2th(weights[f"{root}/{MLP_NORM}/scale"]))
		block.ffn_norm.bias.copy_(np2th(weights[f"{root}/{MLP_NORM}/bias"]))

		block.attn.query.weight.copy_(linear_weight(f"{root}/{ATTENTION_Q}/kernel"))
		block.attn.query.bias.copy_(attention_bias(f"{root}/{ATTENTION_Q}/bias"))
		block.attn.key.weight.copy_(linear_weight(f"{root}/{ATTENTION_K}/kernel"))
		block.attn.key.bias.copy_(attention_bias(f"{root}/{ATTENTION_K}/bias"))
		block.attn.value.weight.copy_(linear_weight(f"{root}/{ATTENTION_V}/kernel"))
		block.attn.value.bias.copy_(attention_bias(f"{root}/{ATTENTION_V}/bias"))
		block.attn.out.weight.copy_(attention_out_weight(f"{root}/{ATTENTION_OUT}/kernel"))
		block.attn.out.bias.copy_(np2th(weights[f"{root}/{ATTENTION_OUT}/bias"]))

		block.ffn.fc1.weight.copy_(linear_weight(f"{root}/{FC_0}/kernel"))
		block.ffn.fc1.bias.copy_(np2th(weights[f"{root}/{FC_0}/bias"]))
		block.ffn.fc2.weight.copy_(linear_weight(f"{root}/{FC_1}/kernel"))
		block.ffn.fc2.bias.copy_(np2th(weights[f"{root}/{FC_1}/bias"]))


	def forward(self, x, mask=None, labels=None, test_mode=False):
		x = self.embeddings(x, mask if self.use_mask else None)

		class_token, useful_features = self.encoder(x)
		part_logits = self.head(class_token)
		if test_mode:
			return part_logits, useful_features
		else:
			loss_fct = CrossEntropyLoss()
			loss = loss_fct(part_logits.view(-1, self.num_classes), labels.view(-1))
			return part_logits, useful_features, loss



class MultiHeadVoting(nn.Module):
	def __init__(self, config, vote_perhead=24):
		super(MultiHeadVoting, self).__init__()
		self.num_heads = config.num_heads
		self.vote_perhead = vote_perhead
		kernel = torch.tensor([[1, 2, 1],
							   [2, 4, 2],
							   [1, 2, 1]], dtype=torch.float32)
		self.register_buffer("kernel", kernel.unsqueeze(0).unsqueeze(0))

	def forward(self, x, select_num=None, enhance=True):
		B, patch_num = x.shape[0], x.shape[3] - 1
		select_num = select_num or self.vote_perhead
		count = torch.zeros((B, patch_num), dtype=x.dtype, device=x.device)

		score = x[:, :, 0, 1:]
		_, select = torch.topk(score, self.vote_perhead, dim=-1)
		select = select.reshape(B, -1)

		for i, b in enumerate(select):
			count[i, :] += torch.bincount(b, minlength=patch_num)

		if enhance:
			count = self.enhace_local(count)

		_, patch_idx = torch.sort(count, dim=-1, descending=True)
		patch_idx += 1
		return patch_idx[:, :select_num]

	def enhace_local(self, count):
		B, H = count.shape[0], math.ceil(math.sqrt(count.shape[1]))
		count = count.reshape(B, H, -1)
		kernel = self.kernel.to(device=count.device, dtype=count.dtype)
		count = F.conv2d(count.unsqueeze(1), kernel, stride=1, padding=1).reshape(B, -1)
		return count





class IEPVEncoder(nn.Module):
	def __init__(self, config, vote_perhead=24):
		super(IEPVEncoder, self).__init__()
		self.layer = nn.ModuleList()
		self.layer_num = config.num_layers
		self.vote_perhead = vote_perhead


		for _ in range(self.layer_num - 1):
			self.layer.append(Block(config))


		self.clr_layer = Block(config)

		self.patch_select = MultiHeadVoting(config, self.vote_perhead)

		self.select_num = 24
		self.count = 0

	def forward(self, hidden_states):
		B, N, C = hidden_states.shape
		complements = [[] for i in range(B)]
		for t in range(self.layer_num - 1):
			layer = self.layer[t]
			hidden_states, weights = layer(hidden_states)
		cls_token = hidden_states[:, 0].unsqueeze(1)
		sort_idx= self.patch_select(weights, select_num=24)


		out = []
		for i in range(B):
			out.append(hidden_states[i, sort_idx[i, :]])
		out = torch.stack(out).squeeze(1)
		out = torch.cat((cls_token, out), dim=1)
		key, weights = self.clr_layer(out)
		return key[:, 0], out




if __name__ == '__main__':
	start = time.time()
	config = get_b16_config()
	net = IEPV(config).cuda()
	x = torch.rand(4, 3, 224, 224, device='cuda')
	m = torch.rand(4, 3, 224, 224, device='cuda')
	y = net(x, m, test_mode=True)
	print(y[0].shape)
	print(y[1].shape)

