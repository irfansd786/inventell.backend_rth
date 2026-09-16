"""Unit and integration tests for Cross-Camera Person Re-ID and Global Identity Manager."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.cv.reid import (
    GlobalIdentityManager,
    GlobalPerson,
    appearance_similarity,
    compute_cross_camera_match,
    compute_zone_similarity,
    extract_appearance_feature,
    global_identity_manager,
    spatial_distance,
)
from app.cv.video_processor import ProcessingJob
from app.main import app
from app.models.user import User
from app.core.dependencies import get_current_user


def test_appearance_feature_and_similarity():
    # Empty or zero cases
    feat_zero = [0.0] * 32
    assert appearance_similarity(feat_zero, feat_zero) == 0.0

    # Identical non-zero vectors
    v1 = [1.0 / (32 ** 0.5)] * 32
    assert pytest.approx(appearance_similarity(v1, v1), 0.001) == 1.0

    # Orthogonal vectors
    v2 = [0.0] * 16 + [1.0 / (16 ** 0.5)] * 16
    v3 = [1.0 / (16 ** 0.5)] * 16 + [0.0] * 16
    assert appearance_similarity(v2, v3) == 0.0

    # Synthetic image feature extraction
    img = np.zeros((100, 50, 3), dtype=np.uint8)
    img[15:55, :] = [120, 200, 200]  # bright upper body
    img[55:95, :] = [30, 40, 50]     # dark lower body
    feat = extract_appearance_feature(img, [5, 5, 45, 95])
    assert len(feat) == 32
    assert any(v > 0 for v in feat)


def test_spatial_and_zone_metrics():
    # Spatial distance
    assert pytest.approx(spatial_distance(10.0, 20.0, 13.0, 24.0), 0.001) == 5.0

    # Zone similarity
    assert compute_zone_similarity({'checkout'}, {'checkout'}) == 1.0
    assert compute_zone_similarity({'aisle'}, {'checkout'}) == 0.80
    assert compute_zone_similarity({'beverages'}, {'personal'}) < 0.80


def test_cross_camera_match_logic():
    v = [1.0 / (32 ** 0.5)] * 32
    t1 = {
        'id': 101,
        'feature': v,
        'first_seen': 0.0,
        'last_seen': 10.0,
        'positions_by_t': {0.0: (20.0, 50.0), 5.0: (22.0, 52.0)},
        'zones': ['checkout', 'aisle'],
    }
    # Similar track in camera 2 at same time and position
    t2_match = {
        'id': 201,
        'feature': v,
        'first_seen': 0.0,
        'last_seen': 10.0,
        'positions_by_t': {0.0: (21.0, 51.0), 5.0: (23.0, 53.0)},
        'zones': ['checkout', 'aisle'],
    }
    res = compute_cross_camera_match(t1, t2_match, threshold=0.70)
    assert res['is_match'] is True
    assert res['confidence'] >= 0.80

    # Disjoint track far away and dissimilar
    v_diff = [0.0] * 16 + [1.0 / (16 ** 0.5)] * 16
    t2_far = {
        'id': 202,
        'feature': v_diff,
        'first_seen': 0.0,
        'last_seen': 10.0,
        'positions_by_t': {0.0: (80.0, 90.0), 5.0: (82.0, 92.0)},
        'zones': ['snacks'],
    }
    res_far = compute_cross_camera_match(t1, t2_far, threshold=0.70)
    assert res_far['is_match'] is False


def test_global_identity_manager_deduplication():
    # Test on the test videos
    j1 = ProcessingJob('camera_01', 'media/test_videos/camera_01.mp4')
    j1.start()
    j2 = ProcessingJob('camera_02', 'media/test_videos/camera_02.mp4')
    j2.start()

    manager = GlobalIdentityManager(threshold=0.55)
    metrics = manager.get_store_metrics(j1, j2, 0.0, 0.0)

    # Core Re-ID Requirement:
    # Deduplicated Store Occupancy MUST be less than simple camera addition (c1 + c2)
    raw_addition = metrics['raw_camera_tracks']
    dedup_occupancy = metrics['store_occupancy']
    assert raw_addition >= 6
    assert dedup_occupancy < raw_addition
    assert metrics['active_matches'] >= 2

    # Check active people have Global IDs and camera tags
    active = metrics['active_people']
    assert len(active) == dedup_occupancy
    assert all('global_id' in p for p in active)
    both_active = [p for p in active if p['active_cameras_label'] == 'BOTH CAMERAS']
    assert len(both_active) >= 2
    assert both_active[0]['is_merged'] is True


def test_store_monitor_api_endpoints():
    mock_user = User(id=1, email="test@example.com", role="MANAGER", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    # 1. Summary endpoint
    res_sum = client.get('/api/store-monitor/summary?t1=0.0&t2=0.0')
    assert res_sum.status_code == 200
    s_data = res_sum.json()
    assert s_data['cross_camera_matching'] is True
    assert 'combined' in s_data
    assert 'global_tracking' in s_data['combined']
    gt = s_data['combined']['global_tracking']
    assert gt['active_people'] > 0
    assert gt['camera_tracks'] > gt['active_people']
    assert gt['cross_camera_matches'] >= 2
    assert gt['status'] == 'ACTIVE (Deduplicated)'

    # 2. Tracks endpoint with Global ID annotation
    res_tracks = client.get('/api/store-monitor/tracks?camera_id=camera_01&timestamp=0.0')
    assert res_tracks.status_code == 200
    tr_data = res_tracks.json()
    assert tr_data['connected'] is True
    assert len(tr_data['people']) > 0
    assert 'global_id' in tr_data['people'][0]
    assert 'global_label' in tr_data['people'][0]
    # Verify both merged (purple) and single-camera (green) people exist
    assert any(p.get('is_merged') is True for p in tr_data['people'])
    assert any(p.get('is_merged') is False for p in tr_data['people'])

    # 3. Global people endpoint
    res_gp = client.get('/api/store-monitor/global-people?t1=0.0&t2=0.0')
    assert res_gp.status_code == 200
    gp_data = res_gp.json()
    assert len(gp_data['people']) >= 2
    assert all(p['is_merged'] for p in gp_data['people'])

    # 4. Global journeys endpoint
    res_gj = client.get('/api/store-monitor/global-journeys?t1=0.0&t2=0.0')
    assert res_gj.status_code == 200
    assert 'items' in res_gj.json()


    app.dependency_overrides.clear()
