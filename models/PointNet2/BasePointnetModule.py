import torch 
import torch.nn as nn  
import torch.nn.functional as F 

import utils.pytorch_utils as pt_utils 
import models.model_utils as md_utils 

from c_lib import FarthestPointSample
from c_lib import QueryBallPoint


class _BasePointnetMSGModule(nn.Module):

    def __init__(self, npoint:int, radius:list[float], nsamples:list[int], mlps:list[list[int]]):
        '''
        npoint : point number for fps sampling
        nsamples : sample point numbers for each radius
        '''
        super().__init__()
        assert len(radius) == len(nsamples) == len(mlps)
        self.npoint = npoint
        self.nsamples = nsamples 
        self.radius = radius
        self.mlps = mlps

        self.fps = FarthestPointSample(npoint)
        self.mlp_layers = nn.ModuleList()
        self.query_ball_point = nn.ModuleList()
        for mlp, radiu, nsample in zip(mlps, radius, nsamples):
            self.mlp_layers.append(pt_utils.SharedMLP(mlp, bn=True))
            self.query_ball_point.append(QueryBallPoint(radiu, nsample))

    def forward(self, pc, feat):
        '''
        input
        ---------------
        pc : B x 3 x N
        feat : B x C x N

        output
        ----------------
        pc_sample : B x 3 x npoint
        feat_sample : B x outchannel x npoint 
        '''
        B, _, N = pc.size()
        idx = self.fps(pc) # B x npoint
        idx = idx.unsqueeze(1).expand(B, 3, self.npoint)
        pc_sample = torch.gather(pc, 2, idx) # B x 3 x npoint
        cat_feat = []

        for i in range(len(self.mlp_layers)):
            indices, _ = self.query_ball_point[i](pc, pc_sample)
            grouped_pc = md_utils._indices_group(pc, indices) # B x 3 x npoint x nsample
            out_feat = grouped_pc
            if feat is not None: # feat will be None in the first layer
                grouped_feat = md_utils._indices_group(feat, indices) # B x C x npoint x nsample
                out_feat = torch.cat([grouped_pc, grouped_feat], dim=1) # B x C+3 x npoint x nsample
            out_feat = self.mlp_layers[i](out_feat)
            out_feat = torch.max(out_feat, -1)[0] # B x C_out x npoint
            cat_feat.append(out_feat)

        cat_feat = torch.cat(cat_feat, dim=1) # B x sum(mlp[-1]) x npoint

        return pc_sample, cat_feat






        
