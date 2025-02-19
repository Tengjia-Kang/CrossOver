import torch
import copy
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Union

def calculate_topK_err_batch(
    src_embed_batch: torch.Tensor, 
    ref_embed_batch: torch.Tensor, 
    mask_batch: torch.Tensor, 
    label_ids: Optional[torch.Tensor] = None, 
    k: int = 3
) -> Union[Tuple[float, float], Tuple[float, float, float, float]]:
    """Calculates top-K error metrics for a batch of embeddings."""
    eff_batch_size = 0
    top1_err_batch, top3_err_batch, same_label_err_batch, diff_label_err_batch  = 0.0, 0.0, 0.0, 0.0
    for idx in range(src_embed_batch.shape[0]):
        errs = calculate_topK_err(src_embed_batch[idx], ref_embed_batch[idx], mask_batch[idx], label_ids[idx] if label_ids is not None else None, k=k)
        if errs is None: 
            continue
        
        top1_err_batch += errs[0]
        top3_err_batch += errs[1]
        if label_ids is not None:
            same_label_err_batch += errs[2]
            diff_label_err_batch += errs[3]
        
        eff_batch_size += 1

    top1_err_batch /= eff_batch_size
    top3_err_batch /= eff_batch_size
    
    if label_ids is not None:
        same_label_err_batch /= eff_batch_size
        diff_label_err_batch /= eff_batch_size
        return top1_err_batch, top3_err_batch, same_label_err_batch, diff_label_err_batch

    return top1_err_batch, top3_err_batch

def calculate_topK_err(
    src_embed: torch.Tensor, 
    ref_embed: torch.Tensor, 
    mask: Optional[torch.Tensor] = None, 
    label_ids: Optional[torch.Tensor] = None, 
    k: int = 3
) -> Optional[Union[Tuple[float, float], Tuple[float, float, float, float]]]:
    """Computes top-K error metrics between source and reference embeddings."""
    if mask is not None:
        src_embed = src_embed[mask]
        ref_embed = ref_embed[mask]
        
        if src_embed.shape[0] == 0: 
            return None
    
    if label_ids is not None: 
        label_ids_masked = label_ids[mask]
    sim = torch.softmax(src_embed @ ref_embed.t(), dim=-1)
    rank_list = torch.argsort(1.0 - sim, dim = 1)
    top_k_indices = rank_list[:, :k]
    
    correct_index = torch.arange(src_embed.shape[0]).unsqueeze(1).to(top_k_indices.device)
    matches = top_k_indices == correct_index    
    top1_err = 1.0 - matches[:, 0].float().mean()
    top3_err = 1.0 - matches.any(dim=1).float().mean()
    
    if label_ids is not None:
        same_label_err, diff_label_err = 0, 0
        for idx in range(top_k_indices.shape[0]):
            if top_k_indices[idx, 0] == idx: 
                continue
            
            same_label_err += int((label_ids_masked[top_k_indices[idx, 0]] == label_ids[idx]))
            diff_label_err += int((label_ids_masked[top_k_indices[idx, 0]] != label_ids[idx]))
        
        same_label_err = same_label_err / top_k_indices.shape[0]
        diff_label_err = diff_label_err / top_k_indices.shape[0]
        
        return top1_err, top3_err, same_label_err, diff_label_err
    return top1_err, top3_err

def calculate_scene_label_recall(
    rank_list: List[List[int]], 
    scene_labels: List[Dict[str, Any]]
) -> Tuple[float, float, float]:
    """Calculates scene label recall metrics at different K values."""
    recall_top1, recall_top5, recall_top10 = 0, 0, 0
    for idx, row in enumerate(rank_list):
        scene_label = scene_labels[idx]['label']
        row_no_self = copy.deepcopy(row)
        row_no_self.remove(idx) 
        
        if scene_labels[row_no_self[0]]['label'] == scene_label:
            recall_top1 += 1
        
        if scene_label in [scene_label['label'] for idx, scene_label in enumerate(scene_labels) if idx in row_no_self[:5]]:
            recall_top5 += 1
        
        if scene_label in [scene_label['label'] for idx, scene_label in enumerate(scene_labels) if idx in row_no_self[:10]]:
            recall_top10 += 1
    
    recall_top1 /= len(scene_labels)
    recall_top5 /= len(scene_labels)
    recall_top10 /= len(scene_labels)
    
    return recall_top1, recall_top5, recall_top10

def evaluate_temporal_scene_matching(
    rank_list: List[List[int]], 
    scan_data: List[Dict[str, Any]], 
    scene_pairs: List[List[Any]]
) -> Tuple[float, float, float]:
    """Evaluates temporal scene matching performance using rank lists."""
    scene_temporal_dict = {}
    
    for scene_pair in scene_pairs:
        ref_scan_id, rescan_list = scene_pair[0], scene_pair[-1]
        if ref_scan_id not in scene_temporal_dict:
            scene_temporal_dict[ref_scan_id] = []
            
        for rescan in rescan_list:
            scene_temporal_dict[ref_scan_id].append(rescan['scan_id'])
        
    recall_top1, recall_top5, recall_top10 = 0, 0, 0
    
    for iter, row in enumerate(rank_list):
        row_no_self = copy.deepcopy(row)
        row_no_self.remove(iter) 
        
        row_scan_id = scan_data[iter]['scan_id']
        
        if row_scan_id not in scene_temporal_dict:
            continue
        
        pred_scan_ids = [scan['scan_id'] for idx, scan in enumerate(scan_data) if idx in row_no_self[:10]]
        
        if pred_scan_ids[0] in scene_temporal_dict[row_scan_id]:
            recall_top1 += 1
        
        if [scan_id for scan_id in scene_temporal_dict[row_scan_id] if scan_id in pred_scan_ids[:5]]:
            recall_top5 += 1
        
        if [scan_id for scan_id in scene_temporal_dict[row_scan_id] if scan_id in pred_scan_ids]:
            recall_top10 += 1
    
    recall_top1 = recall_top1 / len(scene_temporal_dict) * 100.
    recall_top5 = recall_top5 / len(scene_temporal_dict) * 100.
    recall_top10 = recall_top10 / len(scene_temporal_dict) * 100.

    return recall_top1, recall_top5, recall_top10

def evaluate_temporal_instance_matching(scene_pairs: List[List[Any]], outputs: List[Dict[str, Any]]) -> str:
    """Evaluates temporal instance matching on Scan3R."""
    static_recall, dynamic_recall, recall, static_total, dynamic_total, total = 0, 0, 0, 0, 0, 0
    scene_level_total = 0
    scene_level_count = np.zeros(3)
    
    for scene_pair in scene_pairs:
        ref_scan_id, _, rescan_list = scene_pair[0], scene_pair[1], scene_pair[2]
        
        if len(rescan_list) == 0 or ref_scan_id is None: 
            continue
        
        ref_scan_outputs = [output for output in outputs if output['scan_id'] == ref_scan_id]
        if len(ref_scan_outputs) == 0:
            continue
        
        ref_scan_outputs = ref_scan_outputs[0]
        ref_scan_rio_subset_mask = ref_scan_outputs['label_ids_rio_subset_mask']
        
        for rescan in rescan_list:
            rescan_id = rescan['scan_id']
            static_ids = rescan['static_ids']
            moving_ids = rescan['moving_ids']
            
            rescan_outputs = [output for output in outputs if output['scan_id'] == rescan_id][0]
            
            ref_scan_embeds = ref_scan_outputs['point']['embedding']
            
            rescan_embeds = rescan_outputs['point']['embedding']
            rescan_rio_subset_mask = rescan_outputs['label_ids_rio_subset_mask']
            
            refscan_mask = torch.logical_and(ref_scan_outputs['point']['mask'], ref_scan_rio_subset_mask)
            rescan_mask = torch.logical_and(rescan_outputs['point']['mask'], rescan_rio_subset_mask)
            
            refscan_object_ids = ref_scan_outputs['object_ids'][refscan_mask]
            rescan_object_ids = rescan_outputs['object_ids'][rescan_mask]
            ref_scan_embeds = ref_scan_embeds[refscan_mask]
            rescan_embeds  = rescan_embeds[rescan_mask]
            
            sim = torch.softmax(ref_scan_embeds @ rescan_embeds.T, dim=-1)
            rank_list = torch.argsort(1.0 - sim, dim = 1).cpu().numpy()
            
            scene_recall = 0 
            scene_total = 0
            
            for object_idx in range(ref_scan_embeds.shape[0]):
                ref_object_id = refscan_object_ids[object_idx]
                if ref_object_id not in rescan['refscan_ids']: 
                    continue
                
                rescan_pred_lst = rank_list[object_idx]
                rescan_pred_object_ids = [rescan_object_ids[rescan_pred_idx] for rescan_pred_idx in rescan_pred_lst]
                    
                if ref_object_id in static_ids:
                    static_total += 1
                    if ref_object_id == rescan_pred_object_ids[0]:
                        static_recall += 1 
                        recall += 1 
                    
                if ref_object_id in moving_ids:
                    dynamic_total += 1
                    if ref_object_id == rescan_pred_object_ids[0]:
                        dynamic_recall += 1 
                        recall += 1 
                
                scene_total += 1
                scene_recall += 1 if ref_object_id == rescan_pred_object_ids[0] else 0
                total += 1
            
            if scene_total == 0:
                continue
            
            ratio = scene_recall / scene_total
            if  ratio >=0.75: 
                scene_level_count[:] +=1
            elif ratio >=0.5: 
                scene_level_count[1:] +=1
            elif ratio >=0.25: 
                scene_level_count[2:] +=1
            
            scene_level_total += 1

    scene_recall = (scene_level_count / scene_level_total) * 100
    static_recall = (static_recall / static_total) * 100
    dynamic_recall = (dynamic_recall / dynamic_total) * 100
    recall = (recall / total) * 100
    
    message = 'Temporal Instance Matching \n'
    message += f'R@75% - {scene_recall[0]}, R@50% - {scene_recall[1]}, R@25% - {scene_recall[2]} \n'
    message += f'Static: {static_recall}, Dynamic: {dynamic_recall}, All: {recall}'
    return message

def evaluate_intra_category_scene_matching(
    scan_data: List[Dict[str, Any]], 
    src_embed: torch.Tensor, 
    ref_embed: torch.Tensor, 
    unique_labels: List[str]
) -> Tuple[float, float, float]:
    """Evaluates scene matching performance within each category."""
    all_recall_top1, all_recall_top3, all_recall_top5 = [], [], []
    for unique_label in unique_labels:
        label_scan_ids = [idx for idx, data in enumerate(scan_data) if data['label'] == unique_label]
        if len(label_scan_ids) == 0: 
            continue
        
        label_scan_ids_mask = torch.zeros((src_embed.shape[0], ))
        label_scan_ids = torch.tensor(label_scan_ids)    
        label_scan_ids_mask[label_scan_ids] = 1.0
        label_scan_ids_mask = label_scan_ids_mask.bool()
        
        src_embed_masked = src_embed[label_scan_ids_mask.to(src_embed.device)]
        ref_embed_masked = ref_embed[label_scan_ids_mask.to(src_embed.device)]
        sim = torch.softmax(src_embed_masked @ ref_embed_masked.t(), dim=-1)
        rank_list = torch.argsort(1.0 - sim, dim = 1)
        top_k_indices = rank_list[:, :5]
        
        correct_index = torch.arange(src_embed_masked.shape[0]).unsqueeze(1).to(top_k_indices.device)
        matches = top_k_indices == correct_index
        
        recall_top1 = matches[:, 0].float().mean() * 100.
        recall_top3 = matches[:, :3].any(dim=1).float().mean() * 100.
        recall_top5 = matches.any(dim=1).float().mean() * 100.
        
        all_recall_top1.append(recall_top1.item())
        all_recall_top3.append(recall_top3.item())
        all_recall_top5.append(recall_top5.item())
    
    all_recall_top1 = np.array(all_recall_top1)
    all_recall_top3 = np.array(all_recall_top3)
    all_recall_top5 = np.array(all_recall_top5)
    
    return np.mean(all_recall_top1), np.mean(all_recall_top3), np.mean(all_recall_top5)