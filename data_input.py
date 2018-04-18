from __future__ import absolute_import, division, print_function

import tensorflow as tf
import numpy as np
import h5py as h5
import os
from glob import glob
from tqdm import trange
from utils.threadsafe_iter import threadsafe_generator
import re


class DataInput(object):
    """The input data."""
    def __init__(self, config):
        self.data_path = config.data_path
        self.data_set = config.data_set
        self.batch_size = config.batch_size
        self.pick_num = config.pick_num
        self.crop_len = config.crop_len
        self.only_val = config.only_val
        self.data_set_version = config.data_set_version
        self.normalize_data = config.normalize_data
        self.epoch_factor = config.epoch_factor
        self.remove_hip = config.remove_hip

        if self.data_set == "Human36":
            self.used_joints = config.used_joints

        file_path = os.path.join(self.data_path, self.data_set + self.data_set_version + '.h5')
        self.h5file = h5.File(file_path, 'r')
        self.train_keys = [self.data_set + '/Train/' + k
                           for k in self.h5file.get(self.data_set + '/Train').keys()]
        self.val_keys = [self.data_set + '/Validate/' + k
                         for k in self.h5file.get(self.data_set + '/Validate').keys()]

        self.key_pattern = re.compile(".*SEQ(\d+).*")

        # Remove two skel seqs
        if self.data_set == "NTURGBD":
            self.train_keys = [
                key for key in self.train_keys if np.int32(self.h5file[key + '/Action']) < 50
            ]
            self.val_keys = [
                key for key in self.val_keys if np.int32(self.h5file[key + '/Action']) < 50
            ]

        self.len_train_keys = len(self.train_keys)
        self.len_val_keys = len(self.val_keys)

        self.train_epoch_size = (self.len_train_keys // self.batch_size) + 1
        self.val_epoch_size = (self.len_val_keys // self.batch_size) + 1

        self.pshape = [config.njoints, None, 4]
        self.max_plen = config.max_plen

        self.pshape[1] = self.pick_num if self.pick_num > 0 else (self.crop_len if self.crop_len > 0 else None)

        if not self.only_val:
            self.train_batches = self.pre_comp_batches(True)
            self.train_batches *= self.epoch_factor
            self.train_epoch_size *= self.epoch_factor
        self.val_batches = self.pre_comp_batches(False)

    def pre_comp_batches(self, is_training):
        epoch_size = self.train_epoch_size if is_training else self.val_epoch_size
        labs, poses, hip_poses = self.load_to_ram(is_training)

        batches = []
        for slice_idx in range(epoch_size):
            slice_start = slice_idx * self.batch_size
            slice_len = min(slice_start + self.batch_size, labs.shape[0])
            labs_batch = labs[slice_start:slice_len, ...]
            poses_batch = poses[slice_start:slice_len, ...]
            hip_poses_batch = hip_poses[slice_start:slice_len, ...]
            if labs_batch.shape[0] < self.batch_size:
                rand_indices = np.random.random_integers(0, poses.shape[0] - 1, self.batch_size - labs_batch.shape[0])
                labs_batch_extra = labs[rand_indices, ...]
                labs_batch = np.concatenate([labs_batch, labs_batch_extra], axis=0)
                poses_batch_extra = poses[rand_indices, ...]
                poses_batch = np.concatenate([poses_batch, poses_batch_extra], axis=0)
                hip_poses_batch_extra = hip_poses[rand_indices, ...]
                hip_poses_batch = np.concatenate([hip_poses_batch, hip_poses_batch_extra], axis=0)
            batches.append((labs_batch, poses_batch, hip_poses_batch))

        del labs
        del poses
        del hip_poses

        return batches

    def load_to_ram(self, is_training):
        len_keys = self.len_train_keys if is_training else self.len_val_keys
        labs = np.empty([len_keys, 4], dtype=np.int32)
        poses = np.zeros([len_keys, self.pshape[0] + (1 if self.remove_hip else 0), self.max_plen, self.pshape[2]], dtype=np.float32)
        splitname = 'train' if is_training else 'val'
        print('Loading "%s" data to ram...' % splitname)
        t = trange(len_keys, dynamic_ncols=True)
        for k in t:
            seq_idx, subject, action, pose, plen = self.read_h5_data(k, is_training)
            pose = pose[:, :, :self.max_plen] if plen > self.max_plen else pose
            plen = self.max_plen if plen > self.max_plen else plen
            labs[k, :] = [seq_idx, subject, action, plen]
            poses[k, :, :plen, :] = pose

        hip_poses = poses[:, 0, np.newaxis, :, :]
        if self.remove_hip:
            poses = poses[:, 1:, :, :]
            poses[..., :3] = poses[..., :3] - hip_poses[..., :3]

        min_file_path = os.path.join(self.data_path, self.data_set + self.data_set_version + '_poses_mean.npy')
        std_file_path = os.path.join(self.data_path, self.data_set + self.data_set_version + '_poses_std.npy')

        if tf.gfile.Exists(min_file_path) and tf.gfile.Exists(std_file_path):
            self.poses_mean = np.load(min_file_path)
            self.poses_std = np.load(std_file_path)
        else:
            print('Computing mean and std of skels')
            self.poses_mean = np.mean(poses[..., :3], axis=(0, 1, 2), keepdims=True)
            self.poses_std = np.std(poses[..., :3], axis=(0, 1, 2), keepdims=True)
            print(self.poses_mean, self.poses_std)
            np.save(min_file_path, self.poses_mean)
            np.save(std_file_path, self.poses_std)

        if self.normalize_data:
            poses[..., :3] = self.normalize_poses(poses[..., :3])

        return labs, poses, hip_poses

    def read_h5_data(self, key_idx, is_training):
        if is_training:
            key = self.train_keys[key_idx]
        else:
            key = self.val_keys[key_idx]

        subject = np.int32(self.h5file[key+'/Subject']) - 1  # Small hack to reindex the classes from 0
        action = np.int32(self.h5file[key+'/Action']) - 1  # Small hack to reindex the classes from 0
        pose = np.array(self.h5file[key+'/Pose'], dtype=np.float32)

        pose, plen = self.process_pose(pose)

        seq_idx = np.int32(re.match(self.key_pattern, key).group(1))

        return seq_idx, subject, action, pose, plen

    def process_pose(self, pose, plen=None):
        plen = np.int32(np.size(pose, 2)) if plen is None else plen

        if pose.shape[1] > 3:
            pose[:, 3, :] = (pose[:, 3, :] > 0).astype('float32')  # tracking state
        else:
            pose = np.concatenate([pose, np.ones((pose.shape[0], 1, pose.shape[2]))], axis=1)
        pose[np.isnan(pose)] = 0

        if self.data_set == 'NTURGBD':
            pose = pose[:25, :, :]  # Warning: only taking first skeleton
            pose[:, :3, :] = pose[:, :3, :] * 1.0e3  # Rescale to mm
            pose[:, 1, :], pose[:, 2, :] = pose[:, 2, :], pose[:, 1, :]  # Swapping Y-Z coords
        elif self.data_set == 'MSRC12':
            pose[:, :3, :] = pose[:, :3, :] * 1.0e3  # Rescale to mm
            pose[:, 1, :], pose[:, 2, :] = pose[:, 2, :], pose[:, 1, :]  # Swapping Y-Z coords
        elif self.data_set == 'Human36':
            pose = pose[self.used_joints, ...]
            # pose[:, :3, :] = pose[:, :3, :] / 1.0e3 # Rescale to meters

        pose = np.transpose(pose, (0, 2, 1))

        return pose, plen

    def sub_sample_pose(self, pose, hip_pose, plen):

        if self.pick_num > 0:
            if self.pick_num >= plen:
                pose = pose[:, :self.pick_num, :]
                hip_pose = hip_pose[:, :self.pick_num, :]
            elif self.pick_num < plen:
                subplen = plen / self.pick_num
                picks = np.random.randint(0, subplen, size=(self.pick_num)) + \
                        np.arange(0, plen, subplen, dtype=np.int32)
                pose = pose[:, picks, :]
                hip_pose = hip_pose[:, picks, :]
            # plen = np.int32(self.pick_num)
        elif self.crop_len > 0:
            if self.crop_len >= plen:
                pose = pose[:, :self.crop_len, :]
                hip_pose = hip_pose[:, :self.crop_len, :]
            elif self.crop_len < plen:
                indx = np.random.randint(0, plen - self.crop_len)
                pose = pose[:, indx:indx + self.crop_len, :]
                hip_pose = hip_pose[:, indx:indx + self.crop_len, :]
            # plen = np.int32(self.crop_len)

        return pose, hip_pose  #, plen

    def sub_sample_batch(self, batch):
        labs_batch, poses_batch, hip_poses_batch = batch

        if self.pshape[1] is not None:
            new_labs_batch = np.empty([self.batch_size, 4], dtype=np.int32)
            new_poses_batch = np.empty(
                [self.batch_size, self.pshape[0], self.pshape[1], self.pshape[2]], dtype=np.float32)
            new_hip_poses_batch = np.empty(
                [self.batch_size, 1, self.pshape[1], self.pshape[2]], dtype=np.float32)
            new_labs_batch[:, :3] = labs_batch[:, :3]
            new_labs_batch[:, 3] = self.pshape[1]
            for i in range(self.batch_size):
                new_poses_batch[i, ...], new_hip_poses_batch[i, ...] = \
                    self.sub_sample_pose(poses_batch[i, ...], hip_poses_batch[i, ...], labs_batch[i, 3])

            labs_batch = new_labs_batch
            poses_batch = new_poses_batch
            hip_poses_batch = new_hip_poses_batch

        return labs_batch, poses_batch, hip_poses_batch

    @threadsafe_generator
    def batch_generator(self, is_training):
        epoch_size = self.train_epoch_size if is_training else self.val_epoch_size
        batches = self.train_batches if is_training else self.val_batches

        while True:
            rand_indices = np.random.permutation(epoch_size)
            for slice_idx in range(epoch_size):
                if not self.only_val:
                    yield self.sub_sample_batch(batches[rand_indices[slice_idx]])
                else:
                    yield self.sub_sample_batch(batches[slice_idx])

    def normalize_poses(self, poses):
        return (poses - self.poses_mean) / self.poses_std

    def unnormalize_poses(self, poses):
        return (poses * self.poses_std) + self.poses_mean