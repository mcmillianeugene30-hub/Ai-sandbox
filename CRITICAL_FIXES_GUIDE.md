# Critical Security Fixes Implementation Guide

## Overview

This guide provides step-by-step instructions to fix the most critical security vulnerabilities identified in the production readiness audit.

**Estimated Time:** 4-6 hours
**Risk Level:** High (but necessary)
**Testing Required:** Yes

---

## Fix #1: Remove Hardcoded SECRET_KEY (CRITICAL)

### Problem
File: `ai_engine/main.py`, Line 97
```python
SECRET_KEY = os.environ.get("SECRET_KEY", "nexus_super_secret_key_2026")
```

### Solution

**Step 1:** Update `ai_engine/main.py`
```python
# BEFORE
SECRET_KEY = os.environ.get("SECRET_KEY", "nexus_super_secret_key_2026")

# AFTER
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable is required in production. "
        "Generate one with: openssl rand -hex 32"
    )
```

**Step 2:** Generate a secure secret key
```bash
openssl rand -hex 32
# Output example: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

**Step 3:** Add to Encore secrets
```bash
# Using Encore CLI
encore secret set SECRET_KEY --env=production
# Paste the generated key

encore secret set SECRET_KEY --env=preview
# Use a different key for preview
```

**Step 4:** Update `.env.example`
```bash
SECRET_KEY=generate_with_openssl_rand_hex_32
```

**Step 5:** Test locally
```bash
# Should fail if SECRET_KEY not set
unset SECRET_KEY
python ai_engine/main.py  # Should raise ValueError

# Should work if set
export SECRET_KEY="your_test_key_here"
python ai_engine/main.py  # Should start successfully
```

---

## Fix #2: Remove Hardcoded Admin Credentials (CRITICAL)

### Problem
File: `ai_engine/main.py`, Line 252
```python
("nexus", argon2.hash("nexus2026"), 1, "ENTERPRISE", 9_999_999)
```

### Solution

**Step 1:** Update `ai_engine/main.py` - Remove the admin seed
```python
# BEFORE
# Seed admin user (idempotent)
c.execute(
    "INSERT OR IGNORE INTO users (username, hashed_password, is_admin, plan_type, credits) "
    "VALUES (?,?,?,?,?)",
    ("nexus", argon2.hash("nexus2026"), 1, "ENTERPRISE", 9_999_999),
)

# AFTER - Remove or comment out
# Admin creation is now handled by /api/v1/admin/create-admin endpoint
```

**Step 2:** Add admin creation endpoint in `ai_engine/main.py`
```python
class AdminCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12)
    admin_secret: str

# This endpoint can only be called once with a special setup secret
@app.post("/api/v1/admin/create-admin", tags=["Admin"])
async def create_first_admin(req: AdminCreateRequest):
    """
    Create the first admin user. Requires SETUP_SECRET.
    This endpoint is disabled after first admin is created.
    """
    SETUP_SECRET = os.environ.get("SETUP_SECRET")
    if not SETUP_SECRET or req.admin_secret != SETUP_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Invalid setup secret"
        )

    conn = get_conn()
    try:
        # Check if admin already exists
        existing = conn.execute(
            "SELECT id FROM users WHERE is_admin = 1"
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Admin user already exists"
            )

        # Create admin user
        hashed = argon2.hash(req.password)
        conn.execute(
            "INSERT INTO users (username, hashed_password, is_admin, plan_type, credits) "
            "VALUES (?,?,?,?,?)",
            (req.username, hashed, 1, "ENTERPRISE", 9_999_999)
        )
        conn.commit()
        return {"status": "success", "message": "Admin user created"}
    finally:
        conn.close()
```

**Step 3:** Generate SETUP_SECRET
```bash
openssl rand -hex 32
# Example: f1e2d3c4b5a69876fedcba9876543210fedcba9876543210
```

**Step 4:** Add to Encore secrets
```bash
encore secret set SETUP_SECRET --env=production
# Paste the generated setup secret
```

**Step 5:** Update deployment documentation with admin creation steps

---

## Fix #3: Fix SQL Injection in Workspace Creation (CRITICAL)

### Problem
File: `gateway/api.ts`, Line 45
```typescript
await UserDB.exec`INSERT INTO workspaces (user_id, name) VALUES (1, ${req.name})`;
```

### Solution

**Step 1:** Update `gateway/api.ts` - Add authentication
```typescript
// Add user authentication middleware
import { secret } from "encore.dev/config";
import * as jwt from "jsonwebtoken";

const SecretKey = secret("SecretKey");

// Helper function to extract and verify user
async function getUserFromToken(authHeader: string | undefined) {
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
        throw new Error("Missing or invalid authorization header");
    }

    const token = authHeader.substring(7);
    try {
        const decoded = jwt.verify(token, SecretKey()) as any;
        return decoded;
    } catch (err) {
        throw new Error("Invalid token");
    }
}

// Update createWorkspace endpoint
export const createWorkspace = api(
    { method: "POST", path: "/api/v1/workspaces", expose: true },
    async (req: { name: string }, rawReq: Request): Promise<any> => {
        // Extract and verify user from token
        const authHeader = rawReq.headers.get("authorization");
        const user = await getUserFromToken(authHeader);

        // Use authenticated user_id, not hardcoded "1"
        await UserDB.exec`
            INSERT INTO workspaces (user_id, name)
            VALUES (${user.id}, ${req.name})
        `;
        return { status: "created", user_id: user.id };
    }
);
```

**Step 2:** Update listWorkspaces to use authenticated user
```typescript
export const listWorkspaces = api(
    { method: "GET", path: "/api/v1/workspaces", expose: true },
    async (rawReq: Request): Promise<any[]> => {
        const authHeader = rawReq.headers.get("authorization");
        const user = await getUserFromToken(authHeader);

        const rows = UserDB.query`
            SELECT id, name, created_at
            FROM workspaces
            WHERE user_id = ${user.id}
        `;
        const workspaces: any[] = [];
        for await (const row of rows) { workspaces.push(row); }
        return workspaces;
    }
);
```

**Step 3:** Update getWorkspace to check ownership
```typescript
export const getWorkspace = api(
    { method: "GET", path: "/api/v1/workspaces/:id", expose: true },
    async ({ id }: { id: number }, rawReq: Request): Promise<any> => {
        const authHeader = rawReq.headers.get("authorization");
        const user = await getUserFromToken(authHeader);

        // Only return workspaces owned by the user
        const row = await UserDB.queryRow`
            SELECT id, name, config
            FROM workspaces
            WHERE id = ${id} AND user_id = ${user.id}
        `;
        if (!row) {
            throw new Error("Workspace not found or access denied");
        }
        return row;
    }
);
```

**Step 4:** Update updateWorkspace to check ownership
```typescript
export const updateWorkspace = api(
    { method: "PUT", path: "/api/v1/workspaces/:id", expose: true },
    async ({ id, config }: { id: number, config: string }, rawReq: Request): Promise<any> => {
        const authHeader = rawReq.headers.get("authorization");
        const user = await getUserFromToken(authHeader);

        // Only update workspaces owned by the user
        const result = await UserDB.exec`
            UPDATE workspaces
            SET config = ${config}
            WHERE id = ${id} AND user_id = ${user.id}
        `;
        return { status: "updated" };
    }
);
```

---

## Fix #4: Add File Upload Validation (CRITICAL)

### Problem
No validation on uploaded files in `/api/v1/kb/upload` endpoint.

### Solution

**Step 1:** Add file validation utilities in `ai_engine/main.py`
```python
import magic  # python-magic for file type detection
from pathlib import Path

# Allowed file types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".xls", ".xlsx"}

def validate_upload(file: UploadFile) -> tuple[bool, str]:
    """
    Validate uploaded file for type, size, and content.
    Returns (is_valid, error_message)
    """
    # Check file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to beginning

    if file_size > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"

    if file_size == 0:
        return False, "Empty file"

    # Read content to check MIME type
    content = file.file.read(8192)  # Read first 8KB for type detection
    file.file.seek(0)  # Seek back to beginning

    mime_type = magic.from_buffer(content, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid file content type: {mime_type}"

    return True, ""
```

**Step 2:** Update the file upload endpoint
```python
@app.post("/api/v1/kb/upload", tags=["Knowledge Base"])
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: Dict = Depends(get_user)
):
    """Upload document to knowledge base with validation."""

    # Validate file
    is_valid, error_msg = validate_upload(file)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )

    # Sanitize filename
    safe_filename = Path(file.filename).name
    safe_filename = "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in safe_filename)

    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_path = os.path.join(UPLOADS_DIR, unique_filename)

    # Save file
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )

    # Check for malware (optional - requires external service)
    # This is a placeholder for virus scanning integration
    # if has_malware(file_path):
    #     os.remove(file_path)
    #     raise HTTPException(status_code=400, detail="Malicious file detected")

    # Process file with RAG
    try:
        await rag_manager.ingest_document(file_path, user["id"])
    except Exception as e:
        os.remove(file_path)  # Clean up on failure
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )

    return {
        "status": "uploaded",
        "filename": file.filename,
        "file_id": unique_filename
    }
```

**Step 3:** Update requirements.txt to add python-magic
```bash
# Add to requirements.txt
python-magic>=0.4.27
```

**Step 4:** Install system dependencies for python-magic
```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*
```

---

## Fix #5: Implement Secret Management (CRITICAL)

### Problem
Secrets are read from environment variables but there's no rotation or monitoring.

### Solution

**Step 1:** Create secrets configuration file
Create: `ai_engine/config/secrets.py`
```python
import os
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SecretsManager:
    """Manages application secrets with rotation and validation."""

    def __init__(self):
        self._secret_cache = {}
        self._rotation_schedule = {}

    def get_secret(self, key: str, required: bool = True) -> Optional[str]:
        """
        Get secret from environment with caching.
        Raises ValueError if required secret is missing.
        """
        # Check cache
        if key in self._secret_cache:
            secret, expires_at = self._secret_cache[key]
            if expires_at > datetime.now():
                return secret
            # Secret expired, clear cache
            del self._secret_cache[key]

        # Get from environment
        secret = os.environ.get(key)

        if required and not secret:
            raise ValueError(
                f"Required secret '{key}' not found. "
                f"Set it with: encore secret set {key}"
            )

        # Validate secret strength
        if secret and len(secret) < 32:
            logger.warning(
                f"Secret '{key}' appears weak (length < 32). "
                "Consider using a stronger secret."
            )

        # Cache secret with expiration
        if secret:
            self._secret_cache[key] = (
                secret,
                datetime.now() + timedelta(minutes=5)
            )

        return secret

    def validate_required_secrets(self) -> list[str]:
        """
        Validate all required secrets are present.
        Returns list of missing secrets.
        """
        required_secrets = [
            "SECRET_KEY",
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "STRIPE_SECRET_KEY",
        ]

        missing = []
        for secret in required_secrets:
            if not self.get_secret(secret):
                missing.append(secret)

        return missing

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate a secret by updating the cache.
        Note: This doesn't persist to Encore - use Encore CLI for that.
        """
        try:
            self._secret_cache[key] = (
                new_value,
                datetime.now() + timedelta(minutes=5)
            )
            logger.info(f"Secret '{key}' rotated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to rotate secret '{key}': {e}")
            return False

# Global instance
secrets = SecretsManager()
```

**Step 2:** Update `ai_engine/main.py` to use SecretsManager
```python
# At the top of main.py
from config.secrets import secrets

# Replace direct os.environ.get calls
SECRET_KEY = secrets.get_secret("SECRET_KEY")
STRIPE_SECRET_KEY = secrets.get_secret("STRIPE_SECRET_KEY")
GROQ_API_KEY = secrets.get_secret("GROQ_API_KEY")
GEMINI_API_KEY = secrets.get_secret("GEMINI_API_KEY")
OPENROUTER_API_KEY = secrets.get_secret("OPENROUTER_API_KEY")

# Validate all secrets at startup
@app.on_event("startup")
async def validate_secrets():
    missing = secrets.validate_required_secrets()
    if missing:
        raise ValueError(
            f"Missing required secrets: {', '.join(missing)}. "
            "Set them with: encore secret set <SECRET_NAME>"
        )
```

**Step 3:** Create secret rotation script
Create: `scripts/rotate_secrets.sh`
```bash
#!/bin/bash
set -e

echo "🔄 Starting secret rotation..."

# Generate new secrets
NEW_SECRET_KEY=$(openssl rand -hex 32)
echo "✓ Generated new SECRET_KEY"

# Update secrets in Encore
encore secret set SECRET_KEY --env=production <<EOF
$NEW_SECRET_KEY
EOF
echo "✓ Updated SECRET_KEY in production"

# Log rotation
echo "📝 Secret rotation completed at $(date)" >> /var/log/secret_rotation.log

# Trigger service restart (if needed)
# encore app deploy --env=production

echo "✅ Secret rotation complete"
```

**Step 4:** Add scheduled secret rotation (if needed)
```bash
# Add to crontab for weekly rotation
# Run: crontab -e
# Add: 0 0 * * 0 /path/to/scripts/rotate_secrets.sh >> /var/log/secret_rotation.log 2>&1
```

---

## Testing the Fixes

### Test Plan

**1. Test SECRET_KEY removal**
```bash
# Should fail
unset SECRET_KEY
python ai_engine/main.py
# Expected: ValueError about SECRET_KEY

# Should work
export SECRET_KEY="test_secret_key_for_testing"
python ai_engine/main.py
# Expected: Starts successfully
```

**2. Test admin creation**
```bash
# First admin creation
curl -X POST http://localhost:8000/api/v1/admin/create-admin \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123!",
    "admin_secret": "your_setup_secret_here"
  }'
# Expected: {"status": "success", "message": "Admin user created"}

# Second admin creation should fail
curl -X POST http://localhost:8000/api/v1/admin/create-admin \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin2",
    "password": "SecurePassword123!",
    "admin_secret": "your_setup_secret_here"
  }'
# Expected: 400 error "Admin user already exists"
```

**3. Test workspace ownership**
```bash
# Login as user1
TOKEN1=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "password1"}' | jq -r '.access_token')

# Create workspace
curl -X POST http://localhost:8000/api/v1/workspaces \
  -H "Authorization: Bearer $TOKEN1" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Workspace"}'
# Expected: {"status": "created", "user_id": 1}

# Try to access with user2 (should fail)
TOKEN2=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user2", "password": "password2"}' | jq -r '.access_token')

curl -X GET http://localhost:8000/api/v1/workspaces/1 \
  -H "Authorization: Bearer $TOKEN2"
# Expected: 403 or "Workspace not found"
```

**4. Test file upload validation**
```bash
# Test valid file upload
curl -X POST http://localhost:8000/api/v1/kb/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@valid.pdf"
# Expected: 200 success

# Test invalid file type
curl -X POST http://localhost:8000/api/v1/kb/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@malicious.exe"
# Expected: 400 error "Invalid file type"

# Test oversized file
dd if=/dev/zero of=largefile.pdf bs=1M count=15
curl -X POST http://localhost:8000/api/v1/kb/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@largefile.pdf"
# Expected: 400 error "File too large"
```

**5. Test secret validation**
```bash
# Run with missing secrets
unset GROQ_API_KEY
python ai_engine/main.py
# Expected: ValueError about missing GROQ_API_KEY
```

---

## Deployment Checklist

After implementing all fixes:

- [ ] All tests pass locally
- [ ] Secrets are set in Encore for all environments
- [ ] Admin creation endpoint is tested
- [ ] File upload validation is tested with various file types
- [ ] Workspace ownership is tested
- [ ] Secret validation is tested
- [ ] Documentation is updated
- [ ] Team is trained on new admin creation process
- [ ] Secrets rotation schedule is configured (if needed)
- [ ] Monitoring is set up to detect missing secrets

---

## Rollback Plan

If issues occur after deployment:

1. **Secret key issues:** Rollback to previous SECRET_KEY from secrets manager
2. **Admin creation:** Use direct database access to create admin if endpoint fails
3. **Workspace ownership:** Revert gateway/api.ts changes temporarily
4. **File upload:** Disable upload validation temporarily

---

**Estimated Time to Complete:** 4-6 hours
**Priority:** CRITICAL - Must be done before production deployment
**Testing Required:** Yes, comprehensive testing before deployment
