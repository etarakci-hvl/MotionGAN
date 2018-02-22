{
    ## Data Options
    'data_path': '../DMNN/data/',
    # Datasets: MSRC12, NTURGBD
    'data_set': 'NTURGBD',
    'data_set_version': 'v1',
    # Format input as distance matrix
    'format_dm': False,

    ## Model Options
    # Model type to train
    'model_type': 'motiongan',
    # Model version to train
    'model_version': 'v1',
    # Dropout Rate
    'dropout': 0.0,
    # Lambda for gradient penalty
    'lambda_grads': 10,
    # Action label conditional model
    'action_cond': True,
    # Latent factor conditional model, size (0 means no condition)
    'latent_cond_dim': 0,
    # Motion coherence loss
    'coherence_loss': True,
    # Total displacement loss
    'displacement_loss': False,
    # Body shape conservation loss
    'shape_loss': True,
    # Sequence smoothing loss
    'smoothing_loss': True,
    # Time preserving embedding (NOT COMPATIBLE with latent factor model)
    'time_pres_emb': False,
    # Joint unfolding
    'unfold': False,
    # Size of the noise vector
    # 'z_dim': 64,

    ## Training Options
    # It's the batch size
    'batch_size': 256,
    # Final epoch
    'num_epochs': 500,
    # How fast should we learn?
    'learning_rate': 1.0e-3,
    # Train using learning rate decay
    'lr_decay': True,
    # Number of the random picks (0 == deactivated)
    'pick_num': 20,
    # Size of the random crop (0 == deactivated)
    'crop_len': 0,


    ## Environment Options
    # Random inintializer scale
    'init_scale': 0.1,
    # Load pretrained model
    # 'restore_pretrained': False,
    # Pretrained model path
    # 'pretrained_path': None
}
