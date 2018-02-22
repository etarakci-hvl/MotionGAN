from __future__ import absolute_import, division, print_function
import numpy as np
import tensorflow as tf
from config import get_config
from data_input import DataInput
from utils.callbacks import TensorBoard
from models.motiongan import MotionGANV1, MotionGANV2, MotionGANV3
from utils.restore_keras_model import restore_keras_model
from tqdm import trange
from utils.viz import plot_gif

logging = tf.logging
flags = tf.flags
flags.DEFINE_bool("verbose", False, "To talk or not to talk")
flags.DEFINE_string("save_path", None, "Model output directory")
flags.DEFINE_string("config_file", None, "Model config file")
FLAGS = flags.FLAGS

if __name__ == "__main__":
    if not tf.gfile.Exists('./save'):
        tf.gfile.MkDir('./save')

    # Config stuff
    config = get_config(FLAGS)

    data_input = DataInput(config)
    train_batches = data_input.train_epoch_size
    train_generator = data_input.batch_generator(True)
    val_batches = data_input.val_epoch_size
    val_generator = data_input.batch_generator(False)

    # Model building
    if config.model_type == 'motiongan':
        if config.model_version == 'v1':
            model_wrap = MotionGANV1(config)
        if config.model_version == 'v2':
            model_wrap = MotionGANV2(config)
        if config.model_version == 'v3':
            model_wrap = MotionGANV3(config)

    if FLAGS.verbose:
        print('Discriminator model:')
        print(model_wrap.disc_model.summary())
        print('Generator model:')
        print(model_wrap.gen_model.summary())
        print('GAN model:')
        print(model_wrap.gan_model.summary())

    if config.epoch > 0:
        model_wrap.disc_model = restore_keras_model(
            model_wrap.disc_model, config.save_path + '_disc_weights.hdf5', False)
        model_wrap.gen_model = restore_keras_model(
            model_wrap.gen_model, config.save_path + '_gen_weights.hdf5', False)

    tensorboard = TensorBoard(log_dir=config.save_path + '_logs',
                              epoch=config.epoch,
                              n_batches=train_batches,
                              batch_size=config.batch_size,
                              write_graph=True)
    tensorboard.set_model(model_wrap.gan_model)

    def gen_latent_noise():
        return np.random.uniform(size=(config.batch_size, config.latent_cond_dim))

    def save_models():
        model_wrap.disc_model.save(config.save_path + '_disc_weights.hdf5')
        model_wrap.gen_model.save(config.save_path + '_gen_weights.hdf5')

    try:
        for epoch in range(config.epoch, config.num_epochs):
            tensorboard.on_epoch_begin(epoch)

            if config.lr_decay:
                # learning_rate = config.learning_rate * (0.1 ** (epoch // (config.num_epochs // 3)))
                learning_rate = config.learning_rate * (1.0 - (epoch / config.num_epochs))
                model_wrap.update_lr(learning_rate)

            t = trange(config.batch, train_batches)
            t.set_description('| ep: %d | lr: %.2e |' % (epoch, learning_rate))
            disc_loss_sum = 0.0
            gen_loss_sum = 0.0
            for batch in t:
                tensorboard.on_batch_begin(batch)

                disc_batches = 5
                # disc_batches = 55 if ((epoch < 1 and batch < train_batches // 10)
                #                           or (batch % 10 == 0)) else 5
                disc_loss = 0.0
                loss_real = 0.0
                loss_fake = 0.0
                for disc_batch in range(disc_batches):
                    labs_batch, poses_batch = train_generator.next()
                    disc_inputs = [poses_batch]
                    gen_inputs = [poses_batch]
                    place_holders = [True, False]  # disc_training is True, gen_training False
                    if config.action_cond:
                        place_holders.append(labs_batch[:, 2])
                    if config.latent_cond_dim > 0:
                        latent_noise = gen_latent_noise()
                        gen_inputs.append(latent_noise)

                    losses = model_wrap.disc_train(disc_inputs + gen_inputs + place_holders)

                    if disc_batch == 0:
                        disc_losses = losses
                    else:
                        for key in disc_losses.keys():
                            disc_losses[key] += losses[key]

                for key in disc_losses.keys():
                    disc_losses[key] /= train_batches

                labs_batch, poses_batch = train_generator.next()
                gen_inputs = [poses_batch]
                place_holders = [False, True]  # disc_training is False, so gen_training is True
                if config.action_cond:
                    place_holders.append(labs_batch[:, 2])
                if config.latent_cond_dim > 0:
                    latent_noise = gen_latent_noise()
                    gen_inputs.append(latent_noise)

                gen_losses = model_wrap.gen_train(gen_inputs + place_holders)

                # Output to terminal, note output is averaged over the epoch
                disc_loss_sum += disc_losses['train/disc_loss_wgan']
                gen_loss_sum += gen_losses['train/gen_loss_wgan']
                t.set_postfix(disc_loss='%.2e' % (disc_loss_sum / (batch + 1)),
                              gen_loss='%.2e' % (gen_loss_sum / (batch + 1)))

                logs = disc_losses.copy()
                logs.update(gen_losses)

                tensorboard.on_batch_end(batch, logs)

                config.batch = batch + 1
                config.save()

            save_models()

            labs_batch, poses_batch = val_generator.next()
            disc_inputs = [poses_batch]
            gen_inputs = [poses_batch]
            place_holders = [False, False]
            if config.action_cond:
                place_holders.append(labs_batch[:, 2])
            if config.latent_cond_dim > 0:
                latent_noise = gen_latent_noise()
                gen_inputs.append(latent_noise)

            disc_losses = model_wrap.disc_eval(disc_inputs + gen_inputs + place_holders)
            gen_losses = model_wrap.gen_eval(gen_inputs + place_holders)
            gen_outputs = gen_losses.pop('gen_outputs', None)

            logs = disc_losses.copy()
            logs.update(gen_losses)

            # Generating images
            if (epoch % (config.num_epochs // 10)) == 0 or epoch == (config.num_epochs - 1):
                for i in range(16):  # config.batch_size
                    gif_name = '%s_tmp.gif' % config.save_path
                    gif_height, gif_width = plot_gif(poses_batch[i, ...],
                                                     gen_outputs[i, ...],
                                                     labs_batch[i, ...],
                                                     config.data_set, gif_name)

                    with open(gif_name, 'rb') as f:
                        encoded_image_string = f.read()

                    logs['custom_img_%d' % i] = {'height': gif_height,
                                                 'width': gif_width,
                                                 'enc_string': encoded_image_string}

            tensorboard.on_epoch_end(epoch, logs)

            config.epoch = epoch + 1
            config.batch = 0
            config.save()

    except KeyboardInterrupt:
        save_models()

    tensorboard.on_train_end(None)
