import tensorflow as tf
import tensorflow_probability as tfp
import numpy as np
import copy

from .preprocess import rev_trans

class Decoder_AE():

    def __init__(self, loss):
        self.loss = loss
        self.D = None
        self.bias = None
        self.sf = None
        self.rev_trans = 'none'
        
    def get_decoder(self):
        return self.D.numpy(), self.bias.numpy()
        
    def copy(self):
        return copy.copy(self)
    
    def init(self, encoder, feature_means=None, sf=1, trans_func='none'):
        self.D = tf.transpose(encoder.E)
        if feature_means is not None:
            self.bias = feature_means
        else:
            self.bias = np.zeros(adata.n_vars)
        self.bias = tf.convert_to_tensor(self.bias)
        
        self.sf = sf
        self.rev_trans = trans_func

    @tf.function        
    def decode(self, X_latent):
        return Decoder_AE._decode(X_latent, self.D, self.bias, self.sf, self.rev_trans)
        
    @staticmethod
    @tf.function
    def _decode(X_latent, D, bias, sf, trans_fun):
        prediction_no_trans = tf.matmul(tf.convert_to_tensor(X_latent), D)
        prediction_no_trans = tf.gather(prediction_no_trans, tf.range(bias.shape[0]), axis=1)
        prediction_no_trans = tf.math.add(prediction_no_trans, bias)
        prediction = rev_trans(prediction_no_trans, sf, trans_fun)
        return prediction, prediction_no_trans
        
    @tf.function
    def loss_func_d(self, decoder_params, x_latent, x_true, **kwargs):
        x_pred = Decoder_AE._decode(x_latent, D=decoder_params[0], bias=decoder_params[1], sf=self.sf, trans_fun=self.rev_trans)[0]
        return self.loss(x_true, x_pred, **kwargs)
        
    @tf.function
    def lbfgs_input(self, b_and_D, x_latent, x_true, **kwargs):
        b_and_D = tf.reshape(b_and_D, [self.D.shape[0] + 1, self.D.shape[1]])
        x_D = b_and_D[1:, :]
        x_b = b_and_D[0, :]
        loss = self.loss_func_d(decoder_params=[x_D, x_b], x_latent=x_latent, x_true=x_true, **kwargs)
        # gradients = tf.gradients(loss, [x_b, x_D])[0]
        gradients = tf.gradients(loss, b_and_D)[0]
        # x_D = tf.Variable(x_d)
        # x_b = tf.Variable(x_b)
        # with tf.GradientTape() as tape:
        #     loss = self.loss_func_d(decoder_params=[x_D, x_b], x_latent=x_latent, x_true=x_true, **kwargs)
        # gradients = tape.gradient(loss, [x_b, x_D])  ## works in eager mode
        # print(f"D Loss: {loss}")
        # print(f"D Gradients: {gradients}")
        # gradients = tf.concat([tf.expand_dims(gradients[0], 0), gradients[1]], axis=0)
        return loss, tf.clip_by_value(tf.reshape(gradients, [-1]), -100., 100.)
        
    @staticmethod
    def _fit_lbfgs(b_and_D_init, loss, n_parallel):
        
        optim = tfp.optimizer.lbfgs_minimize(loss, 
                                             initial_position=b_and_D_init, 
                                             tolerance=1e-8, 
                                             max_iterations=100, #300, #100,
                                             num_correction_pairs=10, 
                                             parallel_iterations = n_parallel)
        # print(f"D optim converged: {optim.converged}")                                                 
        return optim.position
    
    def fit(self, x_latent, x_true, optimizer, n_parallel, **kwargs):
        
        if optimizer == "lbfgs":
            b_and_D_init = tf.concat([tf.expand_dims(self.bias, 0), self.D], axis=0)
            b_and_D_init = tf.reshape(b_and_D_init, [-1])  ### flatten
            loss = lambda b_and_D: self.lbfgs_input(b_and_D=b_and_D, x_latent=x_latent, x_true=x_true, **kwargs)
            # print(f"D loss init: {self.loss_func_d([self.D, self.bias], x_latent, x_true, **kwargs)}")
            
            optim_results = Decoder_AE._fit_lbfgs(b_and_D_init, loss, n_parallel)
                                            
            b_and_D_out = tf.reshape(optim_results, [self.D.shape[0] + 1, self.D.shape[1]])
            # print(f"b_and_D_out shape: {b_and_D_out.shape[0]}, {b_and_D_out.shape[1]}")
            self.D = tf.convert_to_tensor(b_and_D_out[1:, :])
            self.bias = tf.convert_to_tensor(b_and_D_out[0, :])
            # print(f"D loss final: {self.loss_func_d([self.D, self.bias], x_latent, x_true, **kwargs)}")
                 
        return self.loss_func_d([self.D, self.bias], x_latent, x_true, **kwargs)    
        

class Decoder_PCA():

    def __init__(self, loss):
        self.D = None
        self.bias = None
        self.loss = loss
        
    def init(self, encoder, feature_means=None, sf=1, trans_func='none'):
        self.D = tf.transpose(encoder.E)
        if feature_means is not None:
            self.bias = feature_means
        else:
            self.bias = np.zeros(adata.n_vars)
        self.bias = tf.convert_to_tensor(self.bias)
        
        self.sf = sf
        self.rev_trans = trans_func
        
    @tf.function
    def decode(self, X_latent):
        prediction_no_trans = tf.matmul(tf.convert_to_tensor(X_latent), self.D)
        prediction_no_trans = tf.gather(prediction_no_trans, tf.range(self.bias.shape[0]), axis=1)
        prediction_no_trans = tf.math.add(prediction_no_trans, self.bias)
        prediction = rev_trans(prediction_no_trans, self.sf, self.rev_trans)
        return prediction, prediction_no_trans
        
    def fit(self, **kwargs):
        pass     
    

DECODER_MODELS = {'AE': Decoder_AE, 'PCA': Decoder_PCA}

