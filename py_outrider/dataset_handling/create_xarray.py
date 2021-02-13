import pandas as pd
import numpy as np
import xarray as xr

from ..profile import Profile
from ..distributions import dis_gaussian, dis_log_gaussian, dis_neg_bin
from .input_transform import Trans_sf, Trans_none, Trans_log
from .preprocess import Prepro_sf_log, Prepro_none


class Create_xarray():

    def __init__(self, args_input, X_input=None, sample_anno_input=None):

        if X_input is None:
            X_file = self.read_data_file(args_input["input"])
        else: 
            X_file = self.check_input_matrix(X_input)

        ### create dict to transform to xarray object
        xrds_dict = {
            "X": (("sample", "feature"), X_file.values),
            "X_na": (("sample", "feature"), np.isfinite(X_file).values) # , dtype=float
        }

        xrds_coords = {
            "sample": X_file.index,
            "feature": X_file.columns
        }
        
        ### use sample annotation if supplied
        if (sample_anno_input is not None) or (args_input["sample_anno"] is not None):
            if sample_anno_input is not None:
                sample_anno = self.check_input_sample_anno(sample_anno_input, X_file)
            else:
                sample_anno = self.get_sample_anno(args_input["sample_anno"], X_file)
        
            xrds_dict["sample_anno"] = (("sample", "sample_anno_col"), sample_anno.values.astype(str))
            xrds_coords["sample_anno_col"] = sample_anno.columns

            if args_input["covariates"] is not None:
                cov_sample = self.get_covariates(sample_anno, args_input["covariates"])
                xrds_dict["cov_sample"] = (("sample", "covariates"), cov_sample.values)
                xrds_coords["cov_sample_col"] = cov_sample.columns

        if args_input["X_is_outlier"] is not None:
            X_is_outlier = self.get_X_is_outlier(args_input["X_is_outlier"], X_file)
            X_is_outlier[~xrds_dict["X_na"][1]] = np.nan  # force same nan values as in X
            xrds_dict["X_is_outlier"] = (("sample", "feature"), X_is_outlier.values)

        self.xrds = xr.Dataset(xrds_dict, coords=xrds_coords)

        ### add additional metadata
        for add_attr in ["encod_dim", "num_cpus", "output", "output_list", "float_type",
                         "max_iter", "batch_size", "parallelize_D", "verbose", "output_plots"]:
            self.xrds.attrs[add_attr] = args_input[add_attr]

        self.xrds["sizefactors"] = (("sample"), np.repeat(1, len(self.xrds.coords["sample"])))
        # self.xrds.attrs["float_type"] = self.get_float_type(args_input["float_type"])
        self.xrds.attrs["seed"] = self.get_seed(args_input["seed"])
        self.xrds.attrs["profile"] = self.get_profile(args_input)
        
        # determine if to parallelize D fit (depending on sample size)  (or do depending on feature size?)
        if self.xrds.attrs["parallelize_D"] is None:
            self.xrds.attrs["parallelize_D"] = len(self.xrds.coords["sample"]) > 500

        ### preprocess xrds
        self.xrds.attrs["profile"].prepro.prepro_xrds(self.xrds)


    def read_data_file(self, file_path):
        if file_path is None:
            print(f"file_path specified is None")
            return None
        else:
            data_file = pd.read_csv(file_path, sep=",", header=0, index_col=0).fillna(np.nan)
            return data_file


    def check_input_matrix(self, X_input):
        # check that X_input is pandas DataFrame
        if not isinstance(X_input, pd.DataFrame):
            print(f"X_input has to be a pandas DataFrame!")
            return None
        return X_input
        
    def check_input_sample_anno(self, sample_anno, X_input):
        # check that sample_anno is pandas DataFrame
        if not isinstance(sample_anno, pd.DataFrame):
            print(f"sample_anno has to be a pandas DataFrame!")
            return None
            
        ### find sample_id column
        sample_col_found = None
        for col in sample_anno:
            if set(X_input.index).issubset(sample_anno[col]):
                sample_col_found = col

        if sample_col_found is None:
            raise ValueError("X_input sample names not found in sample_anno_input or not complete")
        elif len(sample_anno[sample_col_found]) != len(set(sample_anno[sample_col_found])):
            raise ValueError(f"duplicates found in sample_anno_input sample_id column: {sample_col_found}")
        else:
            sample_anno.rename(columns={sample_col_found: "sample_id"}, inplace=True)
            sample_anno.set_index(sample_anno["sample_id"], inplace=True)

        ### sort according to X_input and remove unnecessary
        sample_anno = sample_anno.reindex(X_input.index)
        return sample_anno

    def get_sample_anno(self, sa_file_path, X_file):
        sample_anno = self.read_data_file(sa_file_path)  # TODO fix with no index col ?
        ### find sample_id column
        sample_col_found = None
        for col in sample_anno:
            if set(X_file.index).issubset(sample_anno[col]):
                sample_col_found = col

        if sample_col_found is None:
            raise ValueError("input sample names not found in sample_anno or not complete")
        elif len(sample_anno[sample_col_found]) != len(set(sample_anno[sample_col_found])):
            raise ValueError(f"duplicates found in sample_anno sample_id column: {sample_col_found}")
        else:
            sample_anno.rename(columns={sample_col_found: "sample_id"}, inplace=True)
            sample_anno.set_index(sample_anno["sample_id"], inplace=True)

        ### sort according to X_file and remove unnecessary
        sample_anno = sample_anno.reindex(X_file.index)
        return sample_anno


    def get_covariates(self, sample_anno, covariates):
        # TODO HANDLE NAN CASES IN COVARIATES

        if not set(covariates).issubset(sample_anno.columns):
            print(f"INFO: not all covariates could be found in sample_anno (read in names are: {covariates}")

        covariates = [x for x in covariates if x in sample_anno.columns]
        cov_sample = sample_anno[covariates].copy()

        ### transform each cov column to the respective 0|1 code
        for c in cov_sample:
            col = cov_sample[c].astype("category")
            if len(col.cat.categories) == 1:
                cov_sample.drop(c, axis=1, inplace=True, errors="ignore")
            elif len(col.cat.categories) == 2:
                only_01 = [True if x in [0, 1] else False for x in col.cat.categories]
                if all(only_01) is True:
                    # print(f"only_01: {c}")
                    pass
                else:
                    # print(f"2 cat: {c}")
                    oneh = pd.get_dummies(cov_sample[c])
                    cov_sample[c] = oneh.iloc[:, 0]
            else:
                # print(f">2 cat: {c}")
                oneh = pd.get_dummies(cov_sample[c])
                oneh.columns = [c + "_" + str(x) for x in oneh.columns]
                cov_sample.drop(c, axis=1, inplace=True, errors="ignore")
                cov_sample = pd.concat([cov_sample, oneh], axis=1)
        return cov_sample


    def get_X_is_outlier(self, X_is_outlier_path, X_file):
        X_is_outlier_file = self.read_data_file(X_is_outlier_path)
        if X_file.shape != X_is_outlier_file.shape:
            raise ValueError(f"different shapes of X [{X_file.shape}] and X_is_outlier [{X_is_outlier_file.shape}]")
        if not all(X_is_outlier_file.index == X_file.index):
            raise ValueError(f"different rownames of X and X_is_outlier")
        if not all(X_is_outlier_file.columns == X_file.columns):
            raise ValueError(f"different columns of X and X_is_outlier")
        return X_is_outlier_file


    # def get_float_type(self, float_type):
    #     if float_type == "float32":
    #         return np.float32
    #     elif float_type== "float64":
    #         return np.float64
    #     else:
    #         print(f"INFO: float_type {float_type} not found, using float64")
    #         return np.float64


    def get_profile(self, profile):
        prof = Profile(type=profile["profile"].lower())

        ### edit profile if specified in input
        print("checking if profile should be edited")
        if profile["prepro"] is not None:
            prof.prepro = self.get_profile_prepro(profile["prepro"])
        if profile["distribution"] is not None:
            prof.dis = self.get_profile_distribution(profile["distribution"])
        if profile["data_trans"] is not None:
            prof.data_trans = self.get_profile_data_trans(profile["data_trans"])
        if profile["noise_factor"] is not None:
            prof.noise_factor = profile["noise_factor"]
        if profile["loss_dis"] is not None:
            prof.loss_dis = self.get_profile_loss_dis(profile["loss_dis"])

        return prof


    def get_profile_distribution(self, prof_dis):
        if prof_dis.lower() == "neg_bin":
            return dis_neg_bin.Dis_neg_bin
        elif prof_dis.lower() == "gaus":
            return dis_gaussian.Dis_gaussian
        elif prof_dis.lower() == "log_gaus":
            return dis_log_gaussian.Dis_log_gaussian
        else:
            print("dis not found")


    def get_profile_data_trans(self, prof_dt):
        if prof_dt.lower() == "sf":
            return Trans_sf
        elif prof_dt.lower() == "log":
            return Trans_log
        elif prof_dt.lower() == "none":
            return Trans_none
        else:
            print("data_trans not found")


    def get_profile_loss_dis(self, prof_loss):
        if prof_loss.lower() == "neg_bin":
            return dis_neg_bin.Dis_neg_bin
        elif prof_loss.lower() == "gaus":
            return dis_gaussian.Dis_gaussian
        elif prof_loss.lower() == "log_gaus":
            return dis_log_gaussian.Dis_log_gaussian
        else:
            print("loss_dis not found")


    def get_profile_prepro(self, prof_pre):
        if prof_pre.lower() == "sf_log":
            return Prepro_sf_log
        elif prof_pre.lower() == "none":
            return Prepro_none
        else:
            print("prepro not found")


    def get_seed(self, seed):
        if seed < 0:
            return None
        else:
            return seed







