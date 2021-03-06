import torch
import torch.nn as nn
import torch.nn.functional as F

class ConfidenceNllLoss(object):
    """

        Args:
            weights (list of float or None): weight for each scale of estCost.
            max_disp (int): the max of Disparity. default: 192
            sparse (bool): whether the ground-truth disparity is sparse, for example, KITTI is sparse, but SceneFlow is not. default: False

        Inputs:
            estConf (Tensor or list of tensor): the estimated confidence mam, in (BatchSize, 1, Height, Width) layout.
            gtDisp (Tensor): the ground truth disparity map, in (BatchSize, 1, Height, Width) layout.

        Outputs:
            loss (dict), the loss of each level
    """

    def __init__(self, max_disp, weights=None, sparse=False):
        self.max_disp = max_disp
        self.weights = weights
        self.sparse = sparse
        if sparse:
            # sparse disparity ==> max_pooling
            self.scale_func = F.adaptive_max_pool2d
        else:
            # dense disparity ==> avg_pooling
            self.scale_func = F.adaptive_avg_pool2d

    def loss_per_level(self, estConf, gtDisp):
        N, C, H, W = estConf.shape
        scaled_gtDisp = gtDisp
        scale = 1.0
        if gtDisp.shape[-2] != H or gtDisp.shape[-1] != W:
            # compute scale per level and scale gtDisp
            scale = gtDisp.shape[-1] / (W * 1.0)
            scaled_gtDisp = gtDisp / scale
            scaled_gtDisp = self.scale_func(scaled_gtDisp, (H, W))

        # mask for valid disparity
        # gt zero and lt max disparity
        mask = (scaled_gtDisp > 0) & (scaled_gtDisp < (self.max_disp / scale))
        mask = mask.detach_().type_as(gtDisp)
        # NLL loss
        loss = (-1.0 * F.logsigmoid(estConf) * mask).mean()

        return loss

    def __call__(self, estConf, gtDisp):
        if not isinstance(estConf, (list, tuple)):
            estConf = [estConf]

        if self.weights is None:
            self.weights = [1.0] * len(estConf)

        # compute loss for per level
        loss_all_level = [
            self.loss_per_level(est_conf_per_lvl, gtDisp)
            for est_conf_per_lvl in estConf
        ]
        # re-weight loss per level
        weighted_loss_all_level = dict()
        for i, loss_per_level in enumerate(loss_all_level):
            name = "conf_loss_lvl{}".format(i)
            weighted_loss_all_level[name] = self.weights[i] * loss_per_level

        return weighted_loss_all_level

    def __repr__(self):
        repr_str = '{}\n'.format(self.__class__.__name__)
        repr_str += ' ' * 4 + 'Max Disparity: {}\n'.format(self.max_disp)
        repr_str += ' ' * 4 + 'Loss weight: {}\n'.format(self.weights)
        repr_str += ' ' * 4 + 'Disparity is sparse: {}\n'.format(self.sparse)

        return repr_str

    @property
    def name(self):
        return 'ConfidenceNLLLoss'