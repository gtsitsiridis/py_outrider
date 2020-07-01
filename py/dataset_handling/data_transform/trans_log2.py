import numpy as np
import tensorflow as tf    # 2.0.0
from tensorflow import math as tfm
import tensorflow_probability as tfp

from distributions.dis.dis_abstract import Dis_abstract
from dataset_handling.data_transform.trans_abstract import Trans_abstract
from utilis.stats_func import multiple_testing_nan
from distributions.loss_dis.loss_dis_gaussian import Loss_dis_gaussian




class Trans_log2(Trans_abstract):

    trans_name = "trans_log2"


    @staticmethod
    def get_transformed_xrds(xrds):
        return np.log(xrds["X"]+1)
        # return np.log2(xrds["X"] + 1)


    @staticmethod
    def rev_transform(y, **kwargs):
        if tf.is_tensor(y):
            return tfm.exp(y)
        else:
            return np.exp(y)

        # if tf.is_tensor(y):
        #     return tfm.pow(y, 2)
        # else:
        #     return np.power(y, 2)

















