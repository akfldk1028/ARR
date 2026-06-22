# core

Django foundation models for multi-tenancy.

## Models
- `BaseModel` - Abstract base (UUID pk, created_at, updated_at)
- `Organization` - Tenant model (name, slug, settings JSON)
- `OrganizationMember` - User-Org membership (owner/admin/member/viewer roles)
- `Tag` - Generic tagging system (per-organization)

## Usage
```python
from core.models import BaseModel, Organization, Tag
```

All other Django apps inherit from `BaseModel` and reference `Organization`.
