import os.path as osp
import numpy as np
from plyfile import PlyData
from glob import glob
import csv

def get_scan_ids(dirname: str, split: str) -> np.ndarray:
    """Retrieve scan IDs for the given directory and split."""
    filepath = osp.join(dirname, '{}_scans.txt'.format(split))
    scan_ids = np.genfromtxt(filepath, dtype = str)
    return scan_ids

def load_ply_data(data_dir: str, scan_id: str, label_file_name: str) -> np.ndarray:
    """Load PLY data from specified directory, scan ID, and label file."""
    filename_in = osp.join(data_dir, scan_id, label_file_name)
    file = open(filename_in, 'rb')
    ply_data = PlyData.read(file)
    file.close()
    x = ply_data['vertex']['x']
    y = ply_data['vertex']['y']
    z = ply_data['vertex']['z']
    red = ply_data['vertex']['red']
    green = ply_data['vertex']['green']
    blue = ply_data['vertex']['blue']
    object_id = ply_data['vertex']['objectId']
    global_id = ply_data['vertex']['globalId']
    nyu40_id = ply_data['vertex']['NYU40']
    eigen13_id = ply_data['vertex']['Eigen13']
    rio27_id = ply_data['vertex']['RIO27']

    vertices = np.empty(len(x), dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'),  ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'),
                                                     ('objectId', 'h'), ('globalId', 'h'), ('NYU40', 'u1'), ('Eigen13', 'u1'), ('RIO27', 'u1')])
    
    vertices['x'] = x.astype('f4')
    vertices['y'] = y.astype('f4')
    vertices['z'] = z.astype('f4')
    vertices['red'] = red.astype('u1')
    vertices['green'] = green.astype('u1')
    vertices['blue'] = blue.astype('u1')
    vertices['objectId'] = object_id.astype('h')
    vertices['globalId'] = global_id.astype('h')
    vertices['NYU40'] = nyu40_id.astype('u1')
    vertices['Eigen13'] = eigen13_id.astype('u1')
    vertices['RIO27'] = rio27_id.astype('u1')
    
    return vertices

def load_intrinsics(scan_dir: str, type: str = 'color') -> dict:
    """Load intrinsic information for the given scan directory and type."""
    info_path = osp.join(scan_dir, 'sequence', '_info.txt')

    width_search_string = 'm_colorWidth' if type == 'color' else 'm_depthWidth'
    height_search_string = 'm_colorHeight' if type == 'color' else 'm_depthHeight'
    calibration_search_string = 'm_calibrationColorIntrinsic' if type == 'color' else 'm_calibrationDepthIntrinsic'

    with open(info_path) as f:
        lines = f.readlines()
    
    for line in lines:
        if line.find(height_search_string) >= 0:
            intrinsic_height = line[line.find("= ") + 2 :]
        
        elif line.find(width_search_string) >= 0:
            intrinsic_width = line[line.find("= ") + 2 :]
        
        elif line.find(calibration_search_string) >= 0:
            intrinsic_mat = line[line.find("= ") + 2 :].split(" ")

            intrinsic_fx = intrinsic_mat[0]
            intrinsic_cx = intrinsic_mat[2]
            intrinsic_fy = intrinsic_mat[5]
            intrinsic_cy = intrinsic_mat[6]

            intrinsic_mat = np.array([[intrinsic_fx, 0, intrinsic_cx],
                                    [0, intrinsic_fy, intrinsic_cy],
                                    [0, 0, 1]])
            intrinsic_mat = intrinsic_mat.astype(np.float32)
    intrinsics = {'width' : float(intrinsic_width), 'height' : float(intrinsic_height), 
                  'intrinsic_mat' : intrinsic_mat}
    
    return intrinsics

def load_pose(scan_dir: str, frame_id: int) -> np.ndarray:
    """Load pose for a specific frame in the given scan directory."""
    pose_path = osp.join(scan_dir, 'sequence', 'frame-{}.pose.txt'.format(frame_id))
    pose = np.genfromtxt(pose_path)
    return pose

def load_all_poses(scan_dir: str, frame_idxs: list) -> dict:
    """Load all poses for specified frame indices in the scan directory."""
    frame_poses = {}
    for frame_idx in frame_idxs:
        frame_pose = load_pose(scan_dir, frame_idx)
        frame_poses[frame_idx] = frame_pose
    return frame_poses

def load_frame_idxs(scan_dir: str, skip: int = None) -> list:
    """Load frame indices from the scan directory, optionally skipping frames."""
    frames_paths = glob(osp.join(scan_dir, 'sequence', '*.jpg'))
    frame_names = [osp.basename(frame_path) for frame_path in frames_paths]
    frame_idxs = [frame_name.split('.')[0].split('-')[-1] for frame_name in frame_names]
    frame_idxs.sort()

    if skip is None:
        frame_idxs = frame_idxs
    else:
        frame_idxs = [frame_idx for frame_idx in frame_idxs[::skip]]
    return frame_idxs

def read_label_map(file_name: str, label_from: str = 'Global ID', label_to: str = 'Label') -> dict:
    """Read the label map from a CSV file mapping from one label to another."""
    assert osp.exists(file_name)
    
    raw_label_map = read_label_mapping(file_name, label_from=label_from, label_to=label_to)
    return raw_label_map

def read_label_mapping(filename: str, label_from: str = 'Global ID', label_to: str = 'Label') -> dict:
    """Read label mapping from a CSV file, converting keys to integers if applicable."""
    assert osp.isfile(filename)
    mapping = dict()
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')
        for row in reader:
            key = row[label_from].strip()  # Ensure any spaces are stripped
            value = row[label_to].strip()
            mapping[key] = value
    
    if represents_int(list(mapping.keys())[0]):
        mapping = {int(k):v for k,v in mapping.items()}
    
    return mapping

def represents_int(s: str) -> bool:
    """Check if the given string represents an integer."""
    try: 
        int(s)
        return True
    except ValueError:
        return False