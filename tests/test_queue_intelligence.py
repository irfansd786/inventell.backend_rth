"""Unit and integration tests for INVINTELL Queue Intelligence Alert & AI Recommendation System."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.queue_alert import QueueAlert
from app.models.alert import Alert
from app.services import queue_intelligence_service as q_svc

client = TestClient(app)


def test_queue_settings_api():
    """Verify settings endpoint returns configurable thresholds and allows updates."""
    res = client.get('/api/analytics/queue/settings')
    assert res.status_code == 200
    data = res.json()
    assert 'alert_threshold' in data
    assert 'threshold_normal_max' in data
    assert 'threshold_moderate_max' in data
    assert 'threshold_high_max' in data
    assert 'critical_threshold' in data

    # Update threshold
    update_res = client.post('/api/analytics/queue/settings', json={'alert_threshold': 5})
    assert update_res.status_code == 200
    assert update_res.json()['alert_threshold'] == 5

    # Revert to default 6
    client.post('/api/analytics/queue/settings', json={'alert_threshold': 6})


def test_queue_analytics_payload_structure():
    """Verify queue analytics returns structured facts and recommendations."""
    res = client.get('/api/analytics/queue?camera_id=camera_01')
    assert res.status_code == 200
    data = res.json()
    assert 'current_queue' in data
    assert 'queue_threshold' in data
    assert 'queue_status' in data
    assert 'queue_growth' in data
    assert 'average_wait_time' in data
    assert 'peak_queue' in data
    assert 'ai_insight' in data
    assert 'ai_facts' in data
    assert 'cameras_summary' in data
    assert 'recommendation' in data
    assert 'recommendation_reason' in data
    assert 'recent_alerts' in data

    # Facts verification
    facts = data['ai_facts']
    assert 'current_queue_length' in facts
    assert 'queue_threshold' in facts
    assert 'average_wait_time' in facts
    assert 'queue_growth_rate' in facts
    assert 'detection_confidence' in facts


def test_queue_states_logic():
    """Verify dynamic queue states: NORMAL, MODERATE, HIGH, CRITICAL strictly match threshold."""
    # 0..3 -> NORMAL
    assert q_svc._get_state_for_count(1, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'NORMAL'
    assert q_svc._get_state_for_count(3, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'NORMAL'

    # 4..6 -> MODERATE
    assert q_svc._get_state_for_count(4, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'MODERATE'
    assert q_svc._get_state_for_count(5, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'MODERATE'

    # >= alert_threshold -> HIGH
    assert q_svc._get_state_for_count(6, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'HIGH'
    assert q_svc._get_state_for_count(9, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'HIGH'

    # 11+ -> CRITICAL
    assert q_svc._get_state_for_count(11, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'CRITICAL'
    assert q_svc._get_state_for_count(14, alert_thresh=6, n_max=3, m_max=6, h_max=10) == 'CRITICAL'


def test_queue_alert_lifecycle_and_navbar_integration():
    """Verify alert creation, no duplicate spam, and resolution when queue clears."""
    db = SessionLocal()

    # 1. Trigger Alert when threshold is exceeded (e.g. threshold=1)
    res_high = client.get('/api/analytics/queue?camera_id=camera_01&threshold=1')
    assert res_high.status_code == 200
    data_high = res_high.json()
    assert data_high['is_alert'] is True
    assert data_high['queue_status'] in ('HIGH', 'CRITICAL')
    assert 'Open an additional checkout counter' in data_high['recommendation']

    # Verify navbar alert feed has the active queue alert
    nb_res = client.get('/api/alerts?limit=5')
    assert nb_res.status_code == 200
    active_queue_notifs = [a for a in nb_res.json() if a['category'] == 'queue' and not a['is_read']]
    assert len(active_queue_notifs) >= 1
    assert '/queues' in active_queue_notifs[0]['link']

    # 2. Polling again at same high state must NOT create duplicate alerts
    initial_count = db.query(QueueAlert).filter(QueueAlert.status == 'Active').count()
    res_high_2 = client.get('/api/analytics/queue?camera_id=camera_01&threshold=1')
    assert res_high_2.status_code == 200
    subsequent_count = db.query(QueueAlert).filter(QueueAlert.status == 'Active').count()
    assert subsequent_count == initial_count  # NO duplicate created!

    # 3. Queue returns to normal -> alert resolves
    res_norm = client.get('/api/analytics/queue?camera_id=camera_01&threshold=10')
    assert res_norm.status_code == 200
    data_norm = res_norm.json()
    assert data_norm['is_alert'] is False
    assert data_norm['active_alert'] is None

    # Navbar alert for this camera should be marked resolved/read
    resolved_qa = db.query(QueueAlert).filter(QueueAlert.camera_id == 'camera_01').order_by(QueueAlert.id.desc()).first()
    assert resolved_qa.status in ('Resolved', 'Action Dispatched', 'Dismissed')

    db.close()


def test_queue_operational_action_recording():
    """Verify manager action recording endpoint updates alert status and notes."""
    # Create or get an alert
    db = SessionLocal()
    alert = db.query(QueueAlert).first()
    alert_id = alert.id if alert else 1

    action_payload = {'action': 'open_counter', 'notes': 'Manager approved Lane 04 activation'}
    res = client.post(f'/api/analytics/queue/alerts/{alert_id}/action', json=action_payload)
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'success'
    assert 'Open Additional Counter' in data['action_taken']

    # Check alert history endpoint
    hist_res = client.get('/api/analytics/queue/alerts')
    assert hist_res.status_code == 200
    assert len(hist_res.json()) > 0
    db.close()


def test_dual_camera_queue_handling():
    """Verify Camera 01, Camera 02, and Combined unified views are all supported."""
    for cam in ('camera_01', 'camera_02', 'all'):
        res = client.get(f'/api/analytics/queue?camera_id={cam}')
        assert res.status_code == 200
        data = res.json()
        assert data['connected'] is True
        assert 'current_queue' in data
        assert 'cameras_summary' in data