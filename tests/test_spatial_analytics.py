from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user
from app.models.user import User


def test_combined_heatmap_and_zones():
    mock_user = User(id=1, email="test@example.com", role="MANAGER", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    # Test heatmap combined
    res = client.get("/api/analytics/heatmap/combined?metric=traffic&period=today")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "cctvConnected" in data
    assert "kpis" in data
    assert "avgFloorDensity" in data["kpis"]
    assert "peakFloorDensity" in data["kpis"]
    assert "highestTrafficZone" in data["kpis"]
    assert "trackedPoints" in data["kpis"]
    assert "activeSessions" in data["kpis"]
    assert "zones" in data
    assert "topZones" in data
    assert "insights" in data
    assert "meta" in data
    assert "cameras" in data["meta"]
    assert "camera_01" in data["meta"]["cameras"]
    assert "camera_02" in data["meta"]["cameras"]
    assert data["meta"]["cross_camera_matching"] is True

    # Test zones combined
    res_z = client.get("/api/analytics/zones/combined?period=today")
    assert res_z.status_code == 200, res_z.text
    data_z = res_z.json()
    assert "cctvConnected" in data_z
    assert "overviewKpis" in data_z
    assert "activeZones" in data_z["overviewKpis"]
    assert "occupiedZones" in data_z["overviewKpis"]
    assert "highestTrafficZone" in data_z["overviewKpis"]
    assert "highestDwellZone" in data_z["overviewKpis"]
    assert "totalTransitions" in data_z["overviewKpis"]
    assert "zoneMap" in data_z
    assert "bounds" in data_z["zoneMap"]
    assert "table" in data_z
    assert "performance" in data_z
    assert "transitions" in data_z
    assert "customerFlow" in data_z
    assert "dwellAnalysis" in data_z
    assert "operationalAlerts" in data_z
    assert "meta" in data_z
    assert "cameras" in data_z["meta"]
    # Test single-camera filtering
    res_c1 = client.get("/api/analytics/heatmap/combined?camera_id=camera_01&metric=traffic&period=today")
    assert res_c1.status_code == 200, res_c1.text
    data_c1 = res_c1.json()
    assert "densityGrid" in data_c1

    res_zc1 = client.get("/api/analytics/zones/combined?camera_id=camera_01&period=today")
    assert res_zc1.status_code == 200, res_zc1.text
    data_zc1 = res_zc1.json()
    assert "table" in data_zc1

    app.dependency_overrides.clear()
