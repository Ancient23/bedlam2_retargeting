# Copyright (c) 2025 Max Planck Society
# License: https://bedlam2.is.tuebingen.mpg.de/license.html
#
# Export selected SMPL-X animation sequences as npz (SMPL-X orientation format)
#
# Requirements:
# + Enable Python plugin
# + Enable Python Foundation Packages Plugin (numpy)
#
# + Data layout
#   + Folder name of AnimSequence is used to derive the body shape .npz name
#
# Joachim Tesch, Max Planck Institute for Intelligent Systems
#

import numpy as np
from pathlib import Path
import sys
import os
import unreal
import pickle


SMPLX_JOINT_NAMES = [
    'pelvis', 'left_hip', 'right_hip', 'spine1', 'left_knee', 'right_knee', 'spine2', 'left_ankle',
    'right_ankle', 'spine3', 'left_foot', 'right_foot', 'neck', 'left_collar', 'right_collar', 'head',
    'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'jaw',
    'left_eye_smplhf', 'right_eye_smplhf', 'left_index1', 'left_index2', 'left_index3', 'left_middle1',
    'left_middle2', 'left_middle3', 'left_pinky1', 'left_pinky2', 'left_pinky3', 'left_ring1', 'left_ring2',
    'left_ring3', 'left_thumb1', 'left_thumb2', 'left_thumb3', 'right_index1', 'right_index2', 'right_index3',
    'right_middle1', 'right_middle2', 'right_middle3', 'right_pinky1', 'right_pinky2', 'right_pinky3',
    'right_ring1', 'right_ring2', 'right_ring3', 'right_thumb1', 'right_thumb2', 'right_thumb3'
]


def find_first_npz(npz_input_dir, target_name, file_name="motion_seq.npz"):
    for root, dirs, files in os.walk(npz_input_dir):
        if target_name in dirs:
            target_dir = os.path.join(root, target_name)
            for subroot, subdirs, subfiles in os.walk(target_dir):
                for file in subfiles:
                    if file == file_name:
                        return os.path.join(subroot, file)
    return None


def export_to_npz(anim_sequence, out_dir, betas_dict=None):
    dmi = anim_sequence.data_model_interface

    last_frame_index = dmi.get_number_of_frames()  # Will return index of last frame (5.4)
    num_frames = last_frame_index + 1

    frame_rate = dmi.get_frame_rate()
    mocap_frame_rate = float(frame_rate.numerator) / frame_rate.denominator

    options = unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.SOURCE,
                                               should_retarget=False,
                                               extract_root_motion=False,
                                               incorporate_root_motion_into_pose=False,
                                               optional_skeletal_mesh=None,
                                               retrieve_additive_as_full_pose=False,
                                               evaluate_curves=False)

    # (OPTIONAL) Load betas from .pkl if available
    betas = np.zeros(10)
    if betas_dict is not None:
        # The naming convention is: <target_name>+<source_name>_Anim
        target_name = anim_sequence.get_name().split('+')[0]
        unreal.log("Target name: " + target_name)
        # The betas_dict is a dictionary with the target_name as key
        if target_name in betas_dict:
            unreal.log(" Found betas for target.")
            betas = betas_dict[target_name]
        else:
            unreal.log(" No betas found for target. Using zeros.")

    trans = []
    poses = []
    for frame_index in range(num_frames):
        anim_pose = anim_sequence.get_anim_pose_at_frame(frame_index, options)
        smplx_pose = []
        for joint_name in SMPLX_JOINT_NAMES:

            if joint_name == "pelvis":
                pose = anim_pose.get_relative_to_ref_pose_transform(joint_name, space=unreal.AnimPoseSpaces.WORLD)

                translation = pose.translation
                t_x = translation.x / 100
                t_y = -translation.y / 100  # Unreal SMPL-X bind pose Y-axis faces down
                t_z = translation.z / 100
                trans.append([t_x, t_y, t_z])
            else:
                pose = anim_pose.get_relative_to_ref_pose_transform(joint_name, space=unreal.AnimPoseSpaces.LOCAL)

            rotation = pose.rotation
            rotation_axis = rotation.get_rotation_axis()
            rotation_angle = -rotation.get_angle()

            rod_x = rotation_axis.x * rotation_angle
            rod_y = -rotation_axis.y * rotation_angle  # Unreal SMPL-X bind pose Y-axis faces down
            rod_z = rotation_axis.z * rotation_angle

            smplx_pose.append(rod_x)
            smplx_pose.append(rod_y)
            smplx_pose.append(rod_z)

        poses.append(smplx_pose)

    data = {}
    data["gender"] = "neutral"
    data["mocap_frame_rate"] = mocap_frame_rate
    data["model"] = "smplx_locked_head"
    data["betas"] = betas
    data["poses"] = poses
    data["trans"] = trans
    data["info"] = f"Exported from Unreal {unreal.SystemLibrary.get_engine_version()}"

    npz_name = anim_sequence.get_name().replace("_Anim", "") + ".npz"
    target_path = out_dir / npz_name

    unreal.log(f"Exporting: {target_path}")
    np.savez_compressed(str(target_path), **data)
    return True


if __name__ == '__main__':
    unreal.log(f"======================================================================")
    unreal.log(f"Running {__file__}")
    _output_root_dir = Path(sys.argv[1])
    _use_betas_from_pkl_file = bool(int(sys.argv[2]))

    # Load pkl file with the betas (key is the target_name)
    _betas_pkl = None
    if _use_betas_from_pkl_file:
        _output_dir = Path(sys.argv[1]).joinpath("npz_with_betas")
        if len(sys.argv) < 4:
            unreal.log_error("Missing input betas .pkl filepath")
            sys.exit(1)
        _betas_pkl_filepath = sys.argv[3]
        try:
            with open(_betas_pkl_filepath, "rb") as f:
                _betas_pkl = pickle.load(f)
        except Exception as e:
            unreal.log_error(f"Failed to load betas .pkl file: {e}")
            unreal.log_error(f"Please run again without the betas.")
            sys.exit(1)
    else:
        _output_dir = Path(sys.argv[1]).joinpath("npz_without_betas")

    os.makedirs(_output_dir, exist_ok=True)
    unreal.log(f"Export directory: {_output_dir}")

    # Loads all selected assets so very slow operation when selecting whole dataset
    selection = unreal.EditorUtilityLibrary.get_selected_assets()

    processed_sequences = False
    for _asset in selection:
        unreal.log(f"Processing: {_asset.get_name()}")
        if not isinstance(_asset, unreal.AnimSequence):
            unreal.log_warning(" Skipping (not an AnimSequence)")
            continue

        status = export_to_npz(_asset, _output_dir, _betas_pkl)

        if not status:
            unreal.log_error("Failure")
            sys.exit(1)
        else:
            processed_sequences = True

    if not processed_sequences:
        unreal.log_error("No selected AnimSequences")
        sys.exit(1)

    unreal.log("Conversion finished. No errors detected.")
