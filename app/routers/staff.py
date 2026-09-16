import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_permission
from app.core.firebase import (
    create_firebase_user,
    delete_firebase_user,
    send_firebase_password_reset,
)
from app.core.security import get_password_hash
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.staff import (
    EmployeeCreateIn,
    EmployeeProfileOut,
    EmployeeUpdateIn,
    PermissionsUpdateIn,
    StaffListOut,
    StaffListSummary,
)

router = APIRouter(prefix='/staff', tags=['staff'])


def _find_user_by_uid_or_id(db: Session, uid: str) -> User:
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user and uid.isdigit():
        user = db.query(User).filter(User.id == int(uid)).first()
    if not user and uid.startswith('usr_'):
        suffix = uid[4:]
        if suffix.isdigit():
            user = db.query(User).filter(User.id == int(suffix)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Employee {uid} not found')
    return user


@router.get('/me', response_model=EmployeeProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return the profile and assigned permissions for the currently authenticated user."""
    return current_user.to_profile_dict()


@router.get('', response_model=StaffListOut)
def list_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all employee profiles along with aggregate status counts.
    Admin account is separate and not counted in the employee count.
    Requires Admin role or staff permission.
    """
    if not current_user.is_admin and not current_user.has_permission('staff'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Administrator or Staff management permission required',
        )

    # Filter for employee accounts only
    employees = db.query(User).filter(User.role == 'employee').order_by(User.id.asc()).all()

    total = len(employees)
    active = sum(1 for u in employees if u.is_active and u.status == 'active')
    inactive = total - active

    return {
        'summary': {
            'total': total,
            'active': active,
            'inactive': inactive,
            'max_employees': 5,
            'capacity_text': f'{total} / 5',
        },
        'items': [u.to_profile_dict() for u in employees],
    }


@router.post('', response_model=EmployeeProfileOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Create a new employee account in Firebase Authentication and store the authorization profile.
    Enforces maximum limit of 5 employees for this prototype.
    Requires Administrator privileges.
    """
    # Check if email is already registered in database
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'An account with email {payload.email} already exists.',
        )

    # 1. Create Firebase Authentication account server-side
    firebase_uid = create_firebase_user(
        email=payload.email.lower(),
        password=payload.password,
        display_name=payload.name,
    )

    # 2. Store employee profile in database with assigned operational modules
    status_clean = payload.status.lower()
    is_active = status_clean == 'active'

    new_user = User(
        firebase_uid=firebase_uid,
        name=payload.name,
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        role='employee',
        status=status_clean,
        assigned_modules=json.dumps(payload.assigned_modules),
        store=payload.store or 'Main Street Store',
        is_active=is_active,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(new_user)
    db.flush()

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='create_employee',
            entity='staff',
            details=f'Created employee {payload.name} ({payload.email}) with {len(payload.assigned_modules)} modules',
        )
    )
    db.commit()
    db.refresh(new_user)

    return new_user.to_profile_dict()


@router.get('/{uid}', response_model=EmployeeProfileOut)
def get_employee(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve an employee profile by Firebase UID or ID."""
    if not current_user.is_admin and not current_user.has_permission('staff') and current_user.firebase_uid != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Insufficient permissions to inspect employee record',
        )
    user = _find_user_by_uid_or_id(db, uid)
    return user.to_profile_dict()


@router.patch('/{uid}', response_model=EmployeeProfileOut)
def update_employee(
    uid: str,
    payload: EmployeeUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update employee details and assignment. Requires Admin."""
    user = _find_user_by_uid_or_id(db, uid)

    if payload.name is not None:
        user.name = payload.name
    if payload.role is not None:
        user.role = payload.role.lower()
    if payload.status is not None:
        user.status = payload.status.lower()
        user.is_active = user.status == 'active'
    if payload.assigned_modules is not None:
        user.assigned_modules = json.dumps(payload.assigned_modules)
    if payload.store is not None:
        user.store = payload.store

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='update_employee',
            entity='staff',
            details=f'Updated profile for employee {user.email}',
        )
    )
    db.commit()
    db.refresh(user)
    return user.to_profile_dict()


@router.post('/{uid}/activate', response_model=EmployeeProfileOut)
def activate_employee(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate an employee account. Requires Admin."""
    user = _find_user_by_uid_or_id(db, uid)
    user.status = 'active'
    user.is_active = True

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='activate_employee',
            entity='staff',
            details=f'Activated employee {user.email}',
        )
    )
    db.commit()
    db.refresh(user)
    return user.to_profile_dict()


@router.post('/{uid}/deactivate', response_model=EmployeeProfileOut)
def deactivate_employee(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Deactivate an employee account without deleting historical data. Requires Admin."""
    user = _find_user_by_uid_or_id(db, uid)
    user.status = 'inactive'
    user.is_active = False

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='deactivate_employee',
            entity='staff',
            details=f'Deactivated employee {user.email}',
        )
    )
    db.commit()
    db.refresh(user)
    return user.to_profile_dict()


@router.patch('/{uid}/permissions', response_model=EmployeeProfileOut)
def update_permissions(
    uid: str,
    payload: PermissionsUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update assigned modules for an employee. Requires Admin."""
    user = _find_user_by_uid_or_id(db, uid)
    user.assigned_modules = json.dumps(payload.assigned_modules)

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='update_permissions',
            entity='staff',
            details=f'Updated permissions for {user.email}: {payload.assigned_modules}',
        )
    )
    db.commit()
    db.refresh(user)
    return user.to_profile_dict()


@router.post('/{uid}/password-reset')
def trigger_password_reset(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Trigger a Firebase password reset email for the employee.
    Requires Administrator privileges.
    """
    user = _find_user_by_uid_or_id(db, uid)
    send_firebase_password_reset(user.email)

    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='password_reset_requested',
            entity='staff',
            details=f'Triggered password reset email for {user.email}',
        )
    )
    db.commit()
    return {
        'success': True,
        'email': user.email,
        'message': f'Password reset email triggered for {user.email}.',
    }


@router.delete('/{uid}')
def delete_employee(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Permanently delete an employee account from INVINTELL.
    Deletes Firebase user, frees up employee capacity, logs audit record.
    Requires Administrator privileges.
    """
    user = _find_user_by_uid_or_id(db, uid)
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Administrator accounts cannot be deleted through this employee management endpoint.',
        )

    emp_name = user.name
    emp_email = user.email
    fb_uid = user.firebase_uid

    # 1. Delete from Firebase Authentication
    if fb_uid:
        delete_firebase_user(fb_uid)

    # 2. Nullify foreign key references in ActivityLog to prevent FK violation
    db.query(ActivityLog).filter(ActivityLog.user_id == user.id).update({ActivityLog.user_id: None})

    # 3. Record administrative audit log
    db.add(
        ActivityLog(
            user_id=current_user.id,
            action='employee_deleted',
            entity='staff',
            details=f'Deleted employee {emp_name} ({emp_email}) UID: {fb_uid}',
        )
    )

    # 4. Remove user record from database
    db.delete(user)
    db.commit()

    return {
        'success': True,
        'message': f'Employee {emp_name} ({emp_email}) has been permanently deleted.',
        'deleted_uid': uid,
    }

