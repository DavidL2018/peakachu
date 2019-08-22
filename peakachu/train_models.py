#!/usr/bin/env python
from sklearn.externals import joblib
import gc
import pathlib

def main(args):
    import numpy as np
    np.seterr(divide='ignore',invalid='ignore')
    from peakachu import trainUtils
    pathlib.Path(args.output).mkdir(parents=True, exist_ok=True)
    if args.path[-4:]=='.hic':
        hic=True
    else:
        hic=False
    coords = trainUtils.parsebed(args.bedpe,lower=2,res=args.resolution)
    kde, lower, long_start, long_end = trainUtils.learn_distri_kde(coords)
    if not hic:
        import cooler
        Lib = cooler.Cooler(args.path)
        chromosomes=Lib.chromnames[:]
    else:
        import straw
        chromosomes=[str(i) for i in range(1,23)]+['X']
    # train model per chromosome
    positive_class = {}
    negative_class = {}
    for key in chromosomes:
        if key.startswith('chr'):
            chromname=key
        else:
            chromname='chr'+key
        print('collecting from {}'.format(key))
        if not hic:
            X = Lib.matrix(balance=args.balance,sparse=True).fetch(key).tocsr() # lower down the memory usage
        elif args.balance:
            X = straw.straw('KR',args.path,key,key,'BP',args.resolution)
        else:
            X = straw.straw('NONE',args.path,key,key,'BP',args.resolution)
        clist = coords[chromname]

        try:
            positive_class[chromname] = np.vstack((f for f in trainUtils.buildmatrix(
                                             X,clist,width=args.width)))
            neg_coords = trainUtils.negative_generating(X, kde, clist, lower, long_start, long_end)
            stop = len(clist)
            negative_class[chromname]=np.vstack((f for f in trainUtils.buildmatrix(
                             X,neg_coords,width=args.width,
                             positive=False,stop=stop)))
        except:
            print(chromname, ' failed to gather fts')

    for key in chromosomes:
        if key.startswith('chr'):
            chromname=key
        else:
            chromname='chr'+key
 
        Xtrain = np.vstack((v for k,v in positive_class.items() if k!=chromname))
        Xfake = np.vstack((v for k,v in negative_class.items() if k!=chromname))
        print(chromname,'pos/neg: ',Xtrain.shape[0],Xfake.shape[0])
        model = trainUtils.trainRF(Xtrain,Xfake)

        joblib.dump(model, args.output+'/'+chromname+'.pkl', compress=('xz',3))

