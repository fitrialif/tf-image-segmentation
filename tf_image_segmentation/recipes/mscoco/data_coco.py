#!/usr/bin/env python
# coding=utf-8
"""
This is a script for downloading and converting the microsoft coco dataset
from mscoco.org. This can be run as an independent executable to download
the dataset or be imported by scripts used for larger experiments.
"""
from __future__ import division, print_function, unicode_literals
import os
import sys
import zipfile
from collections import defaultdict
from sacred import Experiment, Ingredient
import numpy as np
from PIL import Image
from keras.utils import get_file
from pycocotools.coco import COCO
from tf_image_segmentation.recipes import datasets
from tf_image_segmentation.utils.tf_records import write_image_annotation_pairs_to_tfrecord


# ============== Ingredient 2: dataset =======================
data_coco = Experiment("dataset")


@data_coco.config
def coco_config():
    # TODO(ahundt) add md5 sums for each file
    verbose = True
    dataset_root = os.path.join(os.path.expanduser('~'), 'datasets')
    dataset_path = os.path.join(dataset_root, 'coco')
    urls = [
        'http://msvocds.blob.core.windows.net/coco2014/train2014.zip',
        'http://msvocds.blob.core.windows.net/coco2014/val2014.zip',
        'http://msvocds.blob.core.windows.net/coco2014/test2014.zip',
        'http://msvocds.blob.core.windows.net/coco2015/test2015.zip',
        'http://msvocds.blob.core.windows.net/annotations-1-0-3/instances_train-val2014.zip',
        'http://msvocds.blob.core.windows.net/annotations-1-0-3/person_keypoints_trainval2014.zip',
        'http://msvocds.blob.core.windows.net/annotations-1-0-4/image_info_test2014.zip',
        'http://msvocds.blob.core.windows.net/annotations-1-0-4/image_info_test2015.zip',
        'http://msvocds.blob.core.windows.net/annotations-1-0-3/captions_train-val2014.zip'
    ]
    data_prefixes = [
        'train2014',
        'val2014',
        'test2014',
        'test2015',
    ]
    image_filenames = [prefix + '.zip' for prefix in data_prefixes]
    annotation_filenames = [
        'instances_train-val2014.zip',  # training AND validation info
        'image_info_test2014.zip',  # basic info like download links + category
        'image_info_test2015.zip',  # basic info like download links + category
        'person_keypoints_trainval2014.zip',  # elbows, head, wrist etc
        'captions_train-val2014.zip',  # descriptions of images
    ]
    md5s = [
        '0da8c0bd3d6becc4dcb32757491aca88',  # train2014.zip
        'a3d79f5ed8d289b7a7554ce06a5782b3',  # val2014.zip
        '04127eef689ceac55e3a572c2c92f264',  # test2014.zip
        '65562e58af7d695cc47356951578c041',  # test2015.zip
        '59582776b8dd745d649cd249ada5acf7',  # instances_train-val2014.zip
        '926b9df843c698817ee62e0e049e3753',  # person_keypoints_trainval2014.zip
        'f3366b66dc90d8ae0764806c95e43c86',  # image_info_test2014.zip
        '8a5ad1a903b7896df7f8b34833b61757',  # image_info_test2015.zip
        '5750999c8c964077e3c81581170be65b'   # captions_train-val2014.zip
    ]
    filenames = image_filenames + annotation_filenames
    seg_mask_path = os.path.join(dataset_path, 'seg_mask')
    annotation_json = [
        'annotations/instances_train2014.json',
        'annotations/instances_val2014.json'
    ]
    annotation_paths = [os.path.join(dataset_path, postfix) for postfix in annotation_json]
    # only first two data prefixes contain segmentation masks
    seg_mask_image_paths = [os.path.join(dataset_path, prefix) for prefix in data_prefixes[0:1]]
    seg_mask_output_paths = [os.path.join(seg_mask_path, prefix) for prefix in data_prefixes[0:1]]
    tfrecord_filenames = [os.path.join(dataset_path, prefix + '.tfrecords') for prefix in data_prefixes]
    image_dirs = [os.path.join(dataset_path, prefix) for prefix in data_prefixes]


@data_coco.capture
def coco_files(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths):
    print(dataset_path)
    print(dataset_root)
    print(urls)
    print(filenames)
    print(md5s)
    print(annotation_paths)
    return [os.path.join(dataset_path, file) for file in filenames]


@data_coco.command
def print_coco_files(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths):
    coco_files(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths)


@data_coco.command
def coco_download(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths):
    zip_paths = coco_files(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths)
    for url, filename, md5 in zip(urls, filenames, md5s):
        path = get_file(filename, url, md5_hash=md5, extract=True, cache_subdir=dataset_path)
        # TODO(ahundt) check if it is already extracted, don't re-extract. see
        # https://github.com/fchollet/keras/issues/5861
        zip_file = zipfile.ZipFile(path, 'r')
        zip_file.extractall(path=dataset_path)
        zip_file.close()


@data_coco.command
def coco_json_to_segmentation(seg_mask_output_paths, annotation_paths, seg_mask_image_paths):
    for (seg_mask_path, annFile, image_path) in zip(seg_mask_output_paths, annotation_paths, seg_mask_image_paths):
        coco = COCO(annFile, image_path)
        imgToAnns = defaultdict(list)
        if 'instances' in coco.dataset.keys():
            for ann in coco.dataset['instances']:
                imgToAnns[ann['image_id']].append(ann)
                # anns[ann['id']] = ann
            for img_num in range(len(imgToAnns.keys())):
                # Both [0]'s are used to extract the element from a list
                img = coco.loadImgs(imgToAnns[imgToAnns.keys()[img_num]][0]['image_id'])[0]
                h = img['height']
                w = img['width']
                name = img['file_name']
                root_name = name[:-4]
                MASK = np.zeros((h, w), dtype=np.uint8)
                np.where(MASK > 0)
                for ann in imgToAnns[imgToAnns.keys()[img_num]]:
                    mask = coco.annToMask(ann)
                    ids = np.where(mask > 0)
                    MASK[ids] = ann['category_id']

                im = Image.fromarray(MASK)
                im.save(os.path.join(seg_mask_path, root_name + ".png"))
        elif 'sentences' in coco.dataset.keys():
            print('Skipping due to no instances in annotations,' +
                  ' sentences conversion not supported. Annotations: ' +
                  annotation_paths + ' image_path: ' + image_path)
        else:
            print('Skipping due to no instances in annotations.' +
                  ' Annotations: ' + annotation_paths +
                  ' image_path: ' + image_path)


@data_coco.command
def coco_segmentation_to_tfrecord(tfrecord_filenames, image_dirs,
                                  seg_mask_output_paths):
    # os.environ["CUDA_VISIBLE_DEVICES"] = '1'
    # Get some image/annotation pairs for example
    for tfrecords_filename, img_dir, mask_dir in zip(tfrecord_filenames, image_dirs, seg_mask_output_paths):
        img_list = [os.path.join(img_dir, file) for file in os.listdir(img_dir) if file.endswith('.jpg')]
        mask_list = [os.path.join(mask_dir, file) for file in os.listdir(mask_dir) if file.endswith('.png')]
        filename_pairs = zip(img_list, mask_list)
        # You can create your own tfrecords file by providing
        # your list with (image, annotation) filename pairs here
        write_image_annotation_pairs_to_tfrecord(filename_pairs=filename_pairs,
                                                 tfrecords_filename=tfrecords_filename)


@data_coco.command
def coco_setup(dataset_root, dataset_path, data_prefixes,
               filenames, urls, md5s, tfrecord_filenames, annotation_paths,
               image_dirs, seg_mask_output_paths):
    # download the dataset
    coco_download(dataset_path, filenames, dataset_root, urls, md5s, annotation_paths)
    # convert the relevant files to a more useful format
    coco_json_to_segmentation(seg_mask_output_paths, annotation_paths)
    coco_segmentation_to_tfrecord(tfrecord_filenames, image_dirs,
                                  seg_mask_output_paths)


@data_coco.automain
def main(dataset_root, dataset_path, data_prefixes,
         filenames, urls, md5s, tfrecord_filenames, annotation_paths,
         image_dirs, seg_mask_output_paths):
    coco_config()
    coco_setup(data_prefixes, dataset_path, filenames, dataset_root, urls,
               md5s, tfrecord_filenames, annotation_paths, image_dirs,
               seg_mask_output_paths)