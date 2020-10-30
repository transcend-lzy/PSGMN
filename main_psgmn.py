import os.path as osp
import os
import argparse
import torch
import torch_geometric.transforms as T
from torch_geometric.nn import DataParallel
from torch.utils.data import DataLoader
from dataset.linemod import LineModDataset
from network.psgmn import psgmn
import numpy as np
from eval import evaluator

cuda = torch.cuda.is_available()


def load_network(net, model_dir, resume=True, epoch=-1, strict=False):
    if not resume:
        return 0
    if not os.path.exists(model_dir):
        return 0
    pths = [int(pth.split(".")[0]) for pth in os.listdir(model_dir) if "pkl" in pth]
    if len(pths) == 0:
        return 0
    if epoch == -1:
        pth = max(pths)
    else:
        pth = epoch

    print("Load model: {}".format(os.path.join(model_dir, "{}.pkl".format(pth))))
    pretrained_model = torch.load(os.path.join(model_dir, "{}.pkl".format(pth)))
    net.load_state_dict(pretrained_model, strict=strict)

    return pth


def main(args):

    # load dataset
    train_datasets = []
    test_datasets = []

    train_set = LineModDataset(args.data_path, args.class_type)
    test_set = LineModDataset(
        args.data_path, args.class_type, is_train=False, occ=args.occ
    )

    train_loader = DataLoader(
        train_set, batch_size=args.batch_size, shuffle=True, num_workers=8
    )
    test_loader = DataLoader(test_set, batch_size=args.batch_size, num_workers=8)

    device = torch.device(
        "cuda:0,1,2,3" if cuda else "cpu"
    )  # +re.split(r",",args.gpu_id)[3]
    dnn_model_dir = osp.join("model", args.class_type)
    mesh_model_dir = osp.join(
        args.data_path, "linemod", args.class_type, "{}_new.ply".format(args.class_type)
    )

    psgmnet = psgmn(mesh_model_dir)
    psgmnet = torch.nn.DataParallel(psgmnet, device_ids=[0, 1, 2, 3])
    psgmnet = psgmnet.to(device)
    optimizer = torch.optim.Adam(psgmnet.parameters(), lr=args.lr)

    # code for evaluation
    if args.eval:
        linemod_eval = evaluator(args, psgmnet, test_loader, device)
        load_network(psgmnet, dnn_model_dir, epoch=args.used_epoch)
        linemod_eval.evaluate()
        return


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", type=bool, default=True)
    parser.add_argument("--data_path", type=str, default="./data/")
    parser.add_argument("--class_type", type=str, default="ape")
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--train", type=bool, default=False)
    parser.add_argument("--gpu_id", help="GPU_ID", type=str, default="0,1,2,3")
    parser.add_argument("--occ", type=bool, default=False)
    parser.add_argument("--used_epoch", type=int, default=-1)
    args = parser.parse_args()

    main(args)
