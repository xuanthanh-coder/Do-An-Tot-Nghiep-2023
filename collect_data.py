#!/usr/bin/python

# -*- coding: utf8 -*-

'''
collect data to a csv file

sau khi chạy chương trình, đứng cách xa camera để camera thấy hết các khung xương và thu thập dữ liệu

press 'q' to quit
press others to continue testing other images

This script runs the method from the github repo of "tf-pose-estimation"
https://github.com/ildoonet/tf-pose-estimation
'''
import numpy as np
import cv2
import sys, os, time, argparse, logging
import simplejson
import argparse

import mylib.io as myio
from mylib.display import drawActionResult
from mylib.data_preprocessing import pose_normalization_20

import csv
# PATHS ==============================================================

CURR_PATH = os.path.dirname(os.path.abspath(__file__))+"/"

# INPUTS ==============================================================

def parse_input_FROM_WEBCAM():
    key_word = "--images_source"
    choices = ["webcam", "folder"]

    parser = argparse.ArgumentParser()
    parser.add_argument(key_word, required=False, default='webcam')
    inp = parser.parse_args().images_source
    if inp == "webcam":
        return True
    elif inp == "folder":
        return False
    else:
        print("\nWrong command line input !\n")
        assert True

FROM_WEBCAM = parse_input_FROM_WEBCAM()


# PATHS and SETTINGS =================================

data_idx = "2"
SRC_IMAGE_FOLDER = CURR_PATH + "../data/source_images"+data_idx+"/"
VALID_IMAGES_TXT = "valid_images.txt"

SKELETON_FOLDER = "skeleton_data/"
SAVE_DETECTED_SKELETON_TO =         "skeleton_data/skeletons"+data_idx+"/"
SAVE_DETECTED_SKELETON_IMAGES_TO =  "skeleton_data/skeletons"+data_idx+"_images/"
SAVE_IMAGES_INFO_TO =               "skeleton_data/images_info"+data_idx+".txt"

DO_INFERENCE =  True and FROM_WEBCAM
SAVE_RESULTANT_SKELETON_TO_TXT_AND_IMAGE = not FROM_WEBCAM

# create folders ==============================================================
if not os.path.exists(CURR_PATH+SKELETON_FOLDER):
    os.makedirs(CURR_PATH+SKELETON_FOLDER)
if not os.path.exists(CURR_PATH+SAVE_DETECTED_SKELETON_TO):
    os.makedirs(CURR_PATH+SAVE_DETECTED_SKELETON_TO)
if not os.path.exists(CURR_PATH+SAVE_DETECTED_SKELETON_IMAGES_TO):
    os.makedirs(CURR_PATH+SAVE_DETECTED_SKELETON_IMAGES_TO)

# Openpose ==============================================================

sys.path.append(CURR_PATH + "githubs/tf-pose-estimation")
from tf_pose.networks import get_graph_path, model_wh
from tf_pose.estimator import TfPoseEstimator
from tf_pose import common

logger = logging.getLogger('TfPoseEstimator')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# Human pose detection ==============================================================

class SkeletonDetector(object):
    # This func is copied from https://github.com/ildoonet/tf-pose-estimation

    def __init__(self, model="mobilenet_v2_large"):
        models = set({"mobilenet_thin", "cmu"})
        self.model = model if model in models else "mobilenet_v2_large"
        self.resize_out_ratio = 4.0

        # args = parser.parse_args()

        # w, h = model_wh(args.resize)
        w, h = model_wh("432x368")
        if w == 0 or h == 0:
            e = TfPoseEstimator(get_graph_path(self.model),
                                target_size=(432, 368))
        else:
            e = TfPoseEstimator(get_graph_path(self.model), target_size=(w, h))

        # self.args = args
        self.w, self.h = w, h
        self.e = e
        self.fps_time = time.time()

    def detect(self, image):
        t = time.time()

        # Inference
        humans = self.e.inference(image, resize_to_default=(self.w > 0 and self.h > 0),
                                #   upsample_size=self.args.resize_out_ratio)
                                  upsample_size=self.resize_out_ratio)

        # Print result and time cost
        print("humans:", humans)
        elapsed = time.time() - t
        logger.info('inference image in %.4f seconds.' % (elapsed))

        return humans
    
    def draw(self, img_disp, humans):
        img_disp = TfPoseEstimator.draw_humans(img_disp, humans, imgcopy=False)

        logger.debug('show+')
        cv2.putText(img_disp,
                    "FPS: %f" % (1.0 / (time.time() - self.fps_time)),
                    (20, 20),  cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 255), 2)
        self.fps_time = time.time()

    @staticmethod
    def humans_to_skelsInfo(humans, action_type="None"):
        # skeleton = [action_type, 18*[x,y], 18*score]
        skelsInfo = []
        NaN = 0
        for human in humans:
            skeleton = [NaN]*(1+18*2+18)
            skeleton[0] = action_type
            for i, body_part in human.body_parts.items(): # iterate dict
                idx = body_part.part_idx
                skeleton[1+2*idx]=body_part.x
                skeleton[1+2*idx+1]=body_part.y
                # skeleton[1+36+idx]=body_part.score
            skelsInfo.append(skeleton)
        return skelsInfo

    def humans_to_skelsInfo_choose(humans, joint_choose):
        # skeleton = [action_type, 18*[x,y], 18*score]
        skelsInfo_choose = []
        for human in humans:
            skeleton_choose = []
            for i, body_part in human.body_parts.items(): # iterate dict
                #idx = body_part.part_idx
                for element in joint_choose:
                    if i == element:
                        skeleton_choose.append(body_part.x)
                        skeleton_choose.append(body_part.y)

                print('i: ', i)
                print('body_part.x: ', body_part.x)
                print('body_part.y: ', body_part.y)
            skelsInfo_choose.append(skeleton_choose)
                # skeleton[1+36+idx]=body_part.score
        return skelsInfo_choose
    
    @staticmethod
    def get_ith_skeleton(skelsInfo, ith_skeleton=0):
        return np.array(skelsInfo[ith_skeleton][1:1+18*2])

    def get_ith_skeleton_choose(skelsInfo, ith_skeleton=0):
        return np.array(skelsInfo[ith_skeleton])


# ==============================================================



class DataLoader_usbcam(object):
    def __init__(self):
        self.cam = cv2.VideoCapture(0)
        self.num_images = 9999999

    def load_next_image(self):
        ret_val, img = self.cam.read()
        img =cv2.flip(img, 1)
        action_type = ""
        return img, action_type

class DataLoader_imagesfolder(object):
    def __init__(self, SRC_IMAGE_FOLDER, VALID_IMAGES_TXT):
        self.images_info = myio.collect_images_info_from_source_images(SRC_IMAGE_FOLDER, VALID_IMAGES_TXT)
        self.imgs_path = SRC_IMAGE_FOLDER
        self.i = 0
        self.num_images = len(self.images_info)
        print("Reading images from folder: {}\n".format(SRC_IMAGE_FOLDER))
        print("Reading images information from: {}\n".format(VALID_IMAGES_TXT))
        print("    Num images = {}\n".format(self.num_images))

    def save_images_info(self, path):
        with open(path, 'w') as f:
            simplejson.dump(self.images_info, f)

    def load_next_image(self):
        self.i += 1
        filename = self.get_filename(self.i)
        img = self.imread(self.i)
        action_type = self.get_action_type(self.i)
        return img, action_type

    def imread(self, index):
        return cv2.imread(self.imgs_path + self.get_filename(index))
    
    def get_filename(self, index):
        # [1, 7, 54, "jump", "jump_03-02-12-34-01-795/00240.png"]
        # See "myio.collect_images_info_from_source_images" for the data format
        return self.images_info[index-1][4] 

    def get_action_type(self, index):
        # [1, 7, 54, "jump", "jump_03-02-12-34-01-795/00240.png"]
        # See "myio.collect_images_info_from_source_images" for the data format
        return self.images_info[index-1][3]
        

# ==============================================================

int2str = lambda num, blank: ("{:0"+str(blank)+"d}").format(num)

if __name__ == "__main__":
    joint_choose = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11]
    count_frame = -30

 
    # -- Detect sekelton
    my_detector = SkeletonDetector()

    # -- Load images
    if FROM_WEBCAM:
        images_loader = DataLoader_usbcam()

    else:
        images_loader = DataLoader_imagesfolder(SRC_IMAGE_FOLDER, VALID_IMAGES_TXT)
        images_loader.save_images_info(path = CURR_PATH + SAVE_IMAGES_INFO_TO)

    # -- Loop through all images
    ith_img = 1

    while ith_img <= images_loader.num_images:
        img, action_type = images_loader.load_next_image()
        image_disp = img.copy()

        print("\n\n========================================")
        print("\nProcessing {}/{}th image\n".format(ith_img, images_loader.num_images))

        # Detect skeleton
        humans = my_detector.detect(img)
        skelsInfo_choose = SkeletonDetector.humans_to_skelsInfo_choose(humans, joint_choose)
        skelsInfo = SkeletonDetector.humans_to_skelsInfo(humans)

        print('skelsInfo la: ',skelsInfo)

        for ith_skel in range(0, len(skelsInfo)):        #moi nguoi len(skelsInfo)
            skeleton = SkeletonDetector.get_ith_skeleton(skelsInfo, ith_skel)
            skeleton_choose = SkeletonDetector.get_ith_skeleton_choose(skelsInfo_choose, ith_skel)
            # plt.imshow(skeleton)
            # plt.show()
            print('skeleton: ', skeleton)  #(36,)
            print('====================================================================================================================================================================')
            print('skelInfo_choose: ', skelsInfo_choose)
            print('skeleton_choose: ', skeleton_choose)
            print('len(joint_choose): ', len(skeleton_choose))
            print('====================================================================================================================================================================')


            # Classify action
            if DO_INFERENCE and len(skeleton_choose) == 20: #and len(skeleton_choose) == 20
                count_frame += 1
                if count_frame > 0 and count_frame < 801:
                    cv2.putText(image_disp, 'Bat dau ghi', (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    with open('train_16.csv', 'a') as f:
                        skeleton_choose = skeleton_choose.tolist()
                        skeleton_choose.append(16)
                        writer = csv.writer(f)
                        writer.writerow(skeleton_choose)
                if count_frame > 800:
                    cv2.putText(image_disp, 'Da luu du so sample', (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                prediced_label = action_type
                print("Ground_truth label is :", prediced_label)

            if 1:
                # Draw skeleton
                if ith_skel == 0:
                    my_detector.draw(image_disp, humans)
                
                # Draw bounding box and action type
                drawActionResult(image_disp, skeleton, prediced_label)
        cv2.putText(image_disp, 'frame: %.2f' % count_frame, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # Write result to txt/png
        if SAVE_RESULTANT_SKELETON_TO_TXT_AND_IMAGE:
            myio.save_skeletons(SAVE_DETECTED_SKELETON_TO 
                + int2str(ith_img, 5)+".txt", skelsInfo)
            cv2.imwrite(SAVE_DETECTED_SKELETON_IMAGES_TO 
                + int2str(ith_img, 5)+".png", image_disp)

        if 1: # Display
            cv2.imshow("action_recognition", 
                cv2.resize(image_disp,(0,0),fx=1.5,fy=1.5))
            q = cv2.waitKey(1)
            if q!=-1 and chr(q) == 'q':
                break

        # Loop
        print("\n")
        ith_img += 1

