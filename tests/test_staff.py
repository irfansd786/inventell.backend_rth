from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_staff_list_and_summary():
    response = client.get('/api/staff')
    assert response.status_code == 200
    data = response.json()
    assert 'summary' in data
    assert 'items' in data
    assert data['summary']['total'] == 5
    assert len(data['items']) == 5
    # Ensure all items in staff list are employees (admin is separate)
    for emp in data['items']:
        assert emp['role'] == 'employee'

def test_get_staff_me():
    response = client.get('/api/staff/me')
    assert response.status_code == 200
    data = response.json()
    assert data['email'] == 'admin@invintell.com'
    assert data['role'] == 'admin'
    assert data['status'] == 'active'

def test_activate_and_deactivate_staff():
    response = client.get('/api/staff')
    items = response.json()['items']
    target = items[0]
    uid = target['uid']

    # Deactivate
    deact_resp = client.post(f'/api/staff/{uid}/deactivate')
    assert deact_resp.status_code == 200
    assert deact_resp.json()['status'] == 'inactive'

    # Reactivate
    act_resp = client.post(f'/api/staff/{uid}/activate')
    assert act_resp.status_code == 200
    assert act_resp.json()['status'] == 'active'

def test_update_staff_permissions():
    response = client.get('/api/staff')
    items = response.json()['items']
    target = items[0]
    uid = target['uid']

    new_permissions = ['store_monitor', 'customer_analytics', 'spatial_intelligence']
    patch_resp = client.patch(f'/api/staff/{uid}/permissions', json={'assigned_modules': new_permissions})
    assert patch_resp.status_code == 200
    assert set(patch_resp.json()['assigned_modules']) == set(new_permissions)

def test_employee_limit_enforcement_and_delete():
    # 1. Verify that attempting to add a 6th employee fails with 400
    post_resp = client.post('/api/staff', json={
        'name': 'Extra Test Employee',
        'email': 'extra@invintell.com',
        'password': 'password123',
        'role': 'employee',
        'status': 'active',
        'assigned_modules': ['inventory']
    })
    assert post_resp.status_code == 400
    assert 'limit reached' in post_resp.json()['detail'].lower()

    # 2. Trigger password reset
    staff_resp = client.get('/api/staff')
    target = staff_resp.json()['items'][-1]
    reset_resp = client.post(f"/api/staff/{target['uid']}/password-reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()['success'] is True

    # 3. Delete an employee and verify count becomes 4
    del_resp = client.delete(f"/api/staff/{target['uid']}")
    assert del_resp.status_code == 200
    assert del_resp.json()['success'] is True

    after_del = client.get('/api/staff')
    assert after_del.json()['summary']['total'] == 4

    # 4. Now create replacement employee to restore capacity to 5
    create_resp = client.post('/api/staff', json={
        'name': target['name'],
        'email': target['email'],
        'password': 'password123',
        'role': 'employee',
        'status': 'active',
        'assigned_modules': target['assigned_modules']
    })
    assert create_resp.status_code == 201

    after_create = client.get('/api/staff')
    assert after_create.json()['summary']['total'] == 5
