{
    # Datasets: MSRC12, NTURGBD
    'data_set': 'Human36',
    'data_set_version': 'v1',
    # Model version to train
    'model_version': 'v7',

    # Use pose FAE
    'use_pose_fae': True,
    # Body shape conservation loss
    'shape_loss': True,
    # Rescale coords using skeleton average bone len
    'rescale_coords': True,
    # Translate sequence starting point to 0,0,0
    'translate_start': True,
    # Rotate sequence starting point
    'rotate_start': True,
    # Augment data on training
    'augment_data': True,

    # How fast should we learn?
    'learning_rate': 5.0e-5,
    # It's the batch size
    'batch_size': 64,
    # Multiplies length of epoch, useful for tiny datasets
    'epoch_factor': 256,
    # Number of the random picks (0 == deactivated)
    'pick_num': 20,
    # Size of the random crop (0 == deactivated)
    'crop_len': 100,
}