﻿# Copyright (c) 2018, NVIDIA CORPORATION. All rights reserved.
#
# This work is licensed under the Creative Commons Attribution-NonCommercial
# 4.0 International License. To view a copy of this license, visit
# http://creativecommons.org/licenses/by-nc/4.0/ or send a letter to
# Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import dnnlib
import argparse
import sys
import dnnlib.submission.submit as submit
import validation

# Those first hyper-parameters have to be tuned

NB_CHANNEL = 3
NPY_IMAGES = True
LOG_IMAGES = True


def get_nb_channels():
    """ Assessor for the nb_channels

    :return config.NB_CHANNEL:
    """
    return NB_CHANNEL


def is_image_npy():
    """ Assessor for the boolean if the images are in .npy format

    :return config.NPY_IMAGES:
    """
    return NPY_IMAGES


def is_image_log():
    """ Assessor for the boolean if the images are in log

    :return config.LOG_IMAGES:
    """
    return LOG_IMAGES


# Submit config
# ------------------------------------------------------------------------------------------

submit_config = dnnlib.SubmitConfig()
submit_config.run_dir_root = 'results'
submit_config.run_dir_ignore += ['datasets', 'results']

desc = "autoencoder"

# Tensorflow config
# ------------------------------------------------------------------------------------------

tf_config = dnnlib.EasyDict()
tf_config["graph_options.place_pruned_graph"] = True

# Network config
# ------------------------------------------------------------------------------------------

net_config = dnnlib.EasyDict(func_name="network.autoencoder")

# Optimizer config
# ------------------------------------------------------------------------------------------

optimizer_config = dnnlib.EasyDict(beta1=0.9, beta2=0.99, epsilon=1e-8)

# Noise augmentation config
gaussian_noise_config = dnnlib.EasyDict(
    func_name='train.AugmentGaussian',
    train_stddev_rng_range=(255 * 0.02, 255 * 0.02),     # Original = (0.0, 50.0)
    validation_stddev=255 * 0.020  # Original = 25.0
)
poisson_noise_config = dnnlib.EasyDict(
    func_name='train.AugmentPoisson',
    lam_max=50.0
)
speckle_noise_config = dnnlib.EasyDict(
    func_name='train.AugmentSpeckle',
    l_nb_views=1,
    quick_noise_computation=False
)

# ------------------------------------------------------------------------------------------
# Preconfigured validation sets
datasets = {
    'kodak': dnnlib.EasyDict(dataset_dir='datasets/kodak'),
    'bsd300': dnnlib.EasyDict(dataset_dir='datasets/bsd300'),
    'mva-sar': dnnlib.EasyDict(dataset_dir='datasets/mva-sar'),
    'mva-sar-train': dnnlib.EasyDict(dataset_dir='datasets/mva-sar/train'),
    'mva-sar-val': dnnlib.EasyDict(dataset_dir='datasets/mva-sar/val'),
    'mva-sar-npy-train': dnnlib.EasyDict(dataset_dir='datasets/mva-sar-npy/train'),
    'mva-sar-npy-val': dnnlib.EasyDict(dataset_dir='datasets/mva-sar-npy/val'),
    'mva-sar-npy-3ch-train': dnnlib.EasyDict(dataset_dir='datasets/mva-sar-npy-3ch/train'),
    'mva-sar-npy-3ch-val': dnnlib.EasyDict(dataset_dir='datasets/mva-sar-npy-3ch/val'),
    'set14': dnnlib.EasyDict(dataset_dir='datasets/set14')
}

# Dictionary to link names of validation datasets and their configurations
val_datasets = {
    'default': datasets['kodak'],
    'kodak': datasets['kodak'],
    'mva-sar': datasets['mva-sar-val'],
    'mva-sar-npy': datasets['mva-sar-npy-val'],
    'mva-sar-npy-3ch': datasets['mva-sar-npy-3ch-val']
}

default_validation_config = val_datasets['default']

# Dictionary to link names of noises and their configurations
corruption_types = {
    'gaussian': gaussian_noise_config,
    'poisson': poisson_noise_config,
    'speckle': speckle_noise_config
}

# Train config
# ------------------------------------------------------------------------------------------

train_config = dnnlib.EasyDict(
    iteration_count=120000,  # Value to modify: std=300,000
    eval_interval=1000,
    minibatch_size=4,
    run_func_name="train.train",
    learning_rate=0.0003,
    ramp_down_perc=0.3,
    noise=gaussian_noise_config,
    #    noise=poisson_noise_config,
    noise2noise=True,
    train_tfrecords='datasets/imagenet_val_raw.tfrecords',
    validation_config=default_validation_config
)

# Validation run config
# ------------------------------------------------------------------------------------------
validate_config = dnnlib.EasyDict(
    run_func_name="validation.validate",
    dataset=default_validation_config,
    network_snapshot=None,
    noise=gaussian_noise_config
)


# ------------------------------------------------------------------------------------------

# jhellsten quota group

def error(*print_args):
    print(*print_args)
    sys.exit(1)


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


# ------------------------------------------------------------------------------------------
examples = '''examples:

  # Train a network using the BSD300 dataset:
  python %(prog)s train --train-tfrecords=datasets/bsd300.tfrecords

  # Run a set of images through a pre-trained network:
  python %(prog)s validate --network-snapshot=results/network_final.pickle --dataset-dir=datasets/kodak
'''

if __name__ == "__main__":
    # Defines the functions to be called in case of training, validation of infer
    def train(in_args):
        """ Read the arguments given to train and lauch the training

        :param in_args:
        :return:
        """
        # Reading 'noise2noise" and 'long-run' args
        if in_args:
            n2n = in_args.noise2noise if 'noise2noise' in in_args else True
            train_config.noise2noise = n2n
            if 'long_train' in in_args and in_args.long_train:
                train_config.iteration_count = 500000
                train_config.eval_interval = 1000
                train_config.ramp_down_perc = 0.5
        else:
            print('running with defaults in train_config')

        # Reading 'noise' argument
        noise = 'gaussian'
        if 'noise' in in_args:
            if in_args.noise in corruption_types:
                noise = in_args.noise
            else:
                error('Unknown noise type', in_args.noise)
        train_config.noise = corruption_types[noise]

        # Reading type of training : noise 2 noise or noise 2 clean
        # NB : default == noise 2 noise
        if train_config.noise2noise:
            submit_config.run_desc += "-n2n"
        else:
            submit_config.run_desc += "-n2c"

        # Reading the 'tfrecords' directory argument
        if 'train_tfrecords' in in_args and in_args.train_tfrecords is not None:
            train_config.train_tfrecords = submit.get_path_from_template(in_args.train_tfrecords)

        # Reading the validation directory
        val_dir = 'default'
        if 'val_dir' in in_args:
            if in_args.val_dir not in val_datasets:
                error('Unknown validation directory', in_args.val_dir)
            else:
                val_dir = in_args.val_dir
            train_config.validation_config = val_datasets[val_dir]

        # Finally, printing the config and launching the training
        print(train_config)
        dnnlib.submission.submit.submit_run(submit_config, **train_config)

    # If validation
    def validate(in_args):
        if submit_config.submit_target != dnnlib.SubmitTarget.LOCAL:
            print('Command line overrides currently supported only in local runs for the validate subcommand')
            sys.exit(1)
        if in_args.dataset_dir is None:
            error('Must select dataset with --dataset-dir')
        else:
            validate_config.dataset = {
                'dataset_dir': in_args.dataset_dir
            }
        if in_args.noise not in corruption_types:
            error('Unknown noise type', in_args.noise)
        validate_config.noise = corruption_types[in_args.noise]
        if in_args.network_snapshot is None:
            error('Must specify trained network filename with --network-snapshot')
        validate_config.network_snapshot = in_args.network_snapshot
        dnnlib.submission.submit.submit_run(submit_config, **validate_config)

    # If infer
    def infer_image(in_args):
        if submit_config.submit_target != dnnlib.SubmitTarget.LOCAL:
            print('Command line overrides currently supported only in local runs for the validate subcommand')
            sys.exit(1)
        if in_args.image is None:
            error('Must specify image file with --image')
        if in_args.out is None:
            error('Must specify output image file with --out')
        if in_args.network_snapshot is None:
            error('Must specify trained network filename with --network-snapshot')
        # Note: there's no dnnlib.submission.submit_run here. This is for quick interactive
        # testing, not for long-running training or validation runs.
        validation.infer_image(in_args.network_snapshot, in_args.image, in_args.out)


    # Train by default
    parser = argparse.ArgumentParser(
        description='Train a network or run a set of images through a trained network.',
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--desc', default='', help='Append desc to the run descriptor string')
    parser.add_argument('--run-dir-root',
                        help='Working dir for a training or a validation run. '
                             'Will contain training and validation results.')
    subparsers = parser.add_subparsers(help='Sub-commands', dest='command')

    # Parser Train
    parser_train = subparsers.add_parser('train', help='Train a network')
    parser_train.add_argument('--noise2noise', nargs='?', type=str2bool, const=True, default=True,
                              help='Noise2noise (--noise2noise=true) or noise2clean (--noise2noise=false). '
                                   'Default is noise2noise=true.')
    parser_train.add_argument('--noise', default='gaussian',
                              help='Type of noise corruption (one of: gaussian, poisson)')
    parser_train.add_argument('--long-train', default=False,
                              help='Train for a very long time (500k iterations or 500k*minibatch image)')
    parser_train.add_argument('--train-tfrecords', help='Filename of the training set tfrecords file')
    parser_train.add_argument('--val-dir', default='kodak', help='Validation images directory')
    parser_train.set_defaults(func=train)

    # Parser Validate
    parser_validate = subparsers.add_parser('validate', help='Run a set of images through the network')
    parser_validate.add_argument('--dataset-dir', help='Load all images from a directory (*.png, *.jpg/jpeg, *.bmp)')
    parser_validate.add_argument('--network-snapshot', help='Trained network pickle')
    parser_validate.add_argument('--noise', default='gaussian',
                                 help='Type of noise corruption (one of: gaussian, poisson)')
    parser_validate.set_defaults(func=validate)

    # Parser Infer Image
    parser_infer_image = subparsers.add_parser('infer-image',
                                               help='Run one image through the network without adding any noise')
    parser_infer_image.add_argument('--image', help='Image filename')
    parser_infer_image.add_argument('--out', help='Output filename')
    parser_infer_image.add_argument('--network-snapshot', help='Trained network pickle')
    parser_infer_image.set_defaults(func=infer_image)

    # Reading the given arguments
    args = parser.parse_args()
    submit_config.run_desc = desc + args.desc
    if args.run_dir_root is not None:
        submit_config.run_dir_root = args.run_dir_root
    if args.command is not None:
        args.func(args)
    else:
        # Train if no subcommand was given
        train(args)
