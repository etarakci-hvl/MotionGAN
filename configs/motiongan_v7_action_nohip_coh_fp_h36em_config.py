{
    # Datasets: MSRC12, NTURGBD
    'data_set': 'Human36_expmaps',
    'data_set_version': 'v1',
    # Model version to train
    'model_version': 'v7',
    # Perform per joint normalization
    'normalize_per_joint': True,

    # General loss factor
    # 'loss_factor': 0.1,
    # Remove Hip, use hip relative coordinates
    'remove_hip': True,
    # Action label conditional model
    'action_cond': True,
    # Coherence on generated sequences loss
    'coherence_loss': True,

    # How fast should we learn?
    'learning_rate': 1e-3,
    # It's the batch size
    'batch_size': 128,
    # Multiplies length of epoch, useful for tiny datasets
    'epoch_factor': 256,
    # Number of the random picks (0 == deactivated)
    'pick_num': 20,
    # Size of the random crop (0 == deactivated)
    'crop_len': 200,
    # Train on future prediction task only
    'train_fp': True,
}