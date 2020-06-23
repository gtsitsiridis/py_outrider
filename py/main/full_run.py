
from parser import check_parser
from dataset_handling.create_xarray import Create_xarray
import utilis.stats_func as st
from dataset_handling.ae_dataset import Ae_dataset

class Full_run():

    def __init__(self, args_input):

        args_mod = check_parser.Check_parser(args_input).args_mod
        xrds = Create_xarray(args_mod).xrds
        print(xrds)


        ae_ds = Ae_dataset(xrds)
        ae_model = xrds.attrs["profile"].ae_model(ae_ds)
        xrds = ae_model.run_autoencoder()


        print('ae_model created')

        if xrds.attrs["encod_dim"] is None:
            print('encod_dim is None -> running hyperpar-opt')





        if "X_is_outlier" in xrds:
            pre_rec = st.get_prec_recall(xrds["X_pvalue"].values, xrds["X_is_outlier"].values)
            print(f'precision-recall: { pre_rec["auc"] }')


        ### export
        print(xrds)
        print(xrds["encoder_weights"].shape)
        print(xrds["decoder_weights"].shape)
        xrds.attrs["profile"] = xrds.attrs["profile"].__class__.__name__
        xrds.to_zarr(xrds.attrs["output"] , mode="w")


        # print(xrds)
        # check parser
        # create data set - insert noise, outlier, inject
        # run model
        # calculate statistics
        # plot



        print('finished')













# import os
#
# from utilis_methods import data_handling as dh
#
#
# ### performs outrider python run on folder with counts.csv table from OUTRIDER
#
# class Full_run():
#
#     def __init__(self, ae_class, ds_class, file_path, encoding_dim, output_path, num_cpus, max_iter, float_type,
#                  verbose):
#         self.output_path = dh.path(output_path, 'results_xarr')
#         os.makedirs(self.output_path, exist_ok=True)
#         print(f'results directory = {self.output_path}')
#
#         if not os.listdir(self.output_path):
#             self.exp = ds_class(data_file_path=file_path, encoding_dim=encoding_dim,
#                                 num_cpus=num_cpus, float_type=float_type, verbose=verbose)
#             self.ae = ae_class(self.exp)
#             self.ae.run_autoencoder(max_iter=max_iter)
#             xrds = dh.get_xarr_obj(self.ae)
#             xrds.to_zarr(self.output_path)
#         else:
#             print('ERROR: SELECT AN EMPTY FOLDER OTHERWISE OUTPUT XARRAY CAN NOT BE SAFED')
#             ### TODO fix otherwise
#











