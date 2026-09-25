# Version 2.0 Implementation Plan

## Overview

**Goal:** Secure TechLens demo with GitHub landing page + rate limiting + user signup

**Architecture:**
```
GitHub Landing Page (Static)
    ↓
User enters name/email
    ↓
POST /api/join-demo
    ↓
Backend validates → generates token → returns ngrok URL
    ↓
Auto-redirect to: https://random.ngrok.io/?token=xyz
    ↓
TechLens app validates token → grants access
```

---

## Files to Modify/Create

| File | Action | Why |
|---|---|---|
| `src/techlens/storage/models.py` | **Add** `UserJoined` table | Store signup data |
| `src/techlens/api/routes.py` | **Add** `/api/join-demo` endpoint | Handle user signup |
| `src/techlens/api/main.py` | **Add** rate limiting | Protect from DDoS |
| `src/techlens/config.py` | **Add** token secret | Generate access tokens |
| `frontend/public/join-demo.html` | **Create** GitHub landing page | User signup UI |
| `frontend/src/App.tsx` | **Modify** | Token validation on load |
| `docker-compose.yml` | **Modify** | Update if needed |

---

## Step 1: Add Rate Limiting to FastAPI

**File:** `src/techlens/api/main.py`

**Changes:**
- Import `slowapi` library
- Create limiter instance
- Apply to critical endpoints

**Code to add:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )
```

**Apply to endpoints:**
```python
@router.post("/api/join-demo")
@limiter.limit("5/minute")  # 5 signups per minute per IP
async def join_demo(request: JoinDemoRequest):
    ...

@router.get("/api/digest/daily")
@limiter.limit("30/minute")  # 30 requests per minute per IP
def get_daily_digest(...):
    ...
```

**Install dependency:**
```bash
# In Docker or locally
uv pip install slowapi
```

---

## Step 2: Add UserJoined Table to SQLite

**File:** `src/techlens/storage/models.py`

**Add this class:**
```python
from datetime import datetime, timedelta
import uuid

class UserJoined(Base):
    """User signup record for demo access tracking."""
    __tablename__ = "user_joined"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    def is_token_valid(self) -> bool:
        """Check if token is still valid (not expired)."""
        return datetime.utcnow() < self.token_expires_at
```

**On startup, create the table:**
```python
# In src/techlens/storage/db.py
Base.metadata.create_all(bind=engine)  # Already does this
```

---

## Step 3: Create /api/join-demo Endpoint

**File:** `src/techlens/api/routes.py`

**Add schema:**
```python
from pydantic import BaseModel, EmailStr

class JoinDemoRequest(BaseModel):
    name: str
    email: EmailStr

class JoinDemoResponse(BaseModel):
    access_token: str
    ngrok_url: str
    expires_in_hours: int
    message: str
```

**Add endpoint:**
```python
@router.post("/api/join-demo", response_model=JoinDemoResponse)
@limiter.limit("5/minute")
async def join_demo(request: JoinDemoRequest, session: Session = Depends(get_db)):
    """
    User signup endpoint. Generates temporary access token for demo.
    """
    import os
    from datetime import datetime, timedelta
    import secrets
    
    # Check if user already exists
    existing = session.query(UserJoined).filter_by(email=request.email).first()
    if existing and existing.is_token_valid():
        return JoinDemoResponse(
            access_token=existing.access_token,
            ngrok_url=get_ngrok_url(),  # Function below
            expires_in_hours=24,
            message="Welcome back! Your token is still valid."
        )
    
    # Generate new token
    access_token = secrets.token_urlsafe(32)
    token_expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Store in database
    user = UserJoined(
        name=request.name,
        email=request.email,
        access_token=access_token,
        token_expires_at=token_expires_at
    )
    session.add(user)
    session.commit()
    
    logger.info(f"User joined demo: {request.email}")
    
    return JoinDemoResponse(
        access_token=access_token,
        ngrok_url=get_ngrok_url(),
        expires_in_hours=24,
        message=f"Welcome {request.name}! Your demo access is ready."
    )

def get_ngrok_url() -> str:
    """Get current ngrok URL from file."""
    ngrok_url_file = Path("/home/opc/techlens/current_ngrok_url.txt")
    if ngrok_url_file.exists():
        return ngrok_url_file.read_text().strip()
    return "http://localhost:8000"  # Fallback

@router.get("/api/validate-token")
def validate_token(token: str, session: Session = Depends(get_db)):
    """Check if access token is valid."""
    user = session.query(UserJoined).filter_by(access_token=token).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if not user.is_token_valid():
        raise HTTPException(status_code=401, detail="Token expired")
    
    # Update last accessed time
    user.accessed_at = datetime.utcnow()
    session.commit()
    
    return {
        "valid": True,
        "name": user.name,
        "email": user.email,
        "expires_at": user.token_expires_at
    }
```

---

## Step 4: Add Token Secret to Config

**File:** `src/techlens/config.py`

**Add:**
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Demo access
    demo_access_enabled: bool = True
    token_expiry_hours: int = 24
    ngrok_url: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
```

---

## Step 5: Create GitHub Landing Page

**File:** `frontend/public/join-demo.html`

**Create this file:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TechLens Demo Access</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            padding: 50px 40px;
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.2em;
        }
        .tagline {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .form-group {
            text-align: left;
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #333;
            margin-bottom: 8px;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 1em;
            transition: border-color 0.2s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        .button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .button:hover {
            transform: translateY(-2px);
        }
        .button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            display: none;
        }
        .status.loading {
            display: block;
            background: #e3f2fd;
            color: #1976d2;
        }
        .status.success {
            display: block;
            background: #e8f5e9;
            color: #388e3c;
        }
        .status.error {
            display: block;
            background: #ffebee;
            color: #d32f2f;
        }
        .info {
            color: #999;
            font-size: 0.9em;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 TechLens</h1>
        <p class="tagline">Join the demo to experience AI tech intelligence</p>
        
        <form id="demoForm">
            <div class="form-group">
                <label for="name">Name</label>
                <input type="text" id="name" name="name" required placeholder="Your name">
            </div>
            
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            
            <button type="submit" class="button" id="submitBtn">Join Demo</button>
        </form>
        
        <div class="status" id="status"></div>
        <div class="info">
            ✓ 24-hour demo access<br>
            ✓ No credit card required<br>
            ✓ Secure HTTPS tunnel
        </div>
    </div>

    <script>
        const form = document.getElementById('demoForm');
        const statusDiv = document.getElementById('status');
        const submitBtn = document.getElementById('submitBtn');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const name = document.getElementById('name').value;
            const email = document.getElementById('email').value;
            
            submitBtn.disabled = true;
            showStatus('loading', 'Processing your request...');
            
            try {
                // Call TechLens backend
                const response = await fetch('http://129.146.58.128:8000/api/join-demo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name, email })
                });
                
                if (!response.ok) {
                    throw new Error(`Error: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                // Redirect to TechLens with token
                const demoUrl = `${data.ngrok_url}/?token=${data.access_token}`;
                showStatus('success', `Welcome ${name}! Redirecting to demo...`);
                
                setTimeout(() => {
                    window.location.href = demoUrl;
                }, 2000);
                
            } catch (error) {
                console.error('Error:', error);
                showStatus('error', `Error: ${error.message}. Please try again.`);
                submitBtn.disabled = false;
            }
        });
        
        function showStatus(type, message) {
            statusDiv.className = `status ${type}`;
            statusDiv.textContent = message;
        }
    </script>
</body>
</html>
```

---

## Step 6: Modify Frontend App.tsx for Token Validation

**File:** `frontend/src/App.tsx`

**Add token validation on app load:**
```typescript
import { useEffect, useState } from 'react';

function App() {
    const [authenticated, setAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        // Get token from URL
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');
        
        if (!token) {
            // No token, redirect to landing page
            window.location.href = '/join-demo.html';
            return;
        }
        
        // Validate token
        fetch(`/api/validate-token?token=${token}`)
            .then(res => {
                if (res.ok) {
                    setAuthenticated(true);
                    // Remove token from URL for cleanliness
                    window.history.replaceState({}, document.title, window.location.pathname);
                } else {
                    alert('Invalid or expired token. Please join the demo again.');
                    window.location.href = '/join-demo.html';
                }
            })
            .catch(err => {
                console.error('Token validation failed:', err);
                window.location.href = '/join-demo.html';
            })
            .finally(() => setLoading(false));
    }, []);
    
    if (loading) {
        return <div>Validating access...</div>;
    }
    
    if (!authenticated) {
        return <div>Redirecting...</div>;
    }
    
    // Rest of your App component
    return (
        // ... existing app content ...
    );
}

export default App;
```

---

## Step 7: Update pyproject.toml

**Add slowapi dependency:**
```toml
dependencies = [
    # ... existing ...
    "slowapi>=0.1.9",
]
```

---

## Installation & Testing

### Install new dependency:
```bash
cd ~/techlens
uv sync
```

### Update Docker:
```bash
docker compose build --no-cache techlens
docker compose down
docker compose up -d
```

### Test the flow:
1. Visit `https://your-github-pages-url/join-demo.html` (static, always available)
2. Enter name and email
3. Click "Join Demo"
4. Should redirect to: `https://random.ngrok.io/?token=xyz`
5. TechLens app validates token and grants access

### Test rate limiting:
```bash
# Make 31 requests to same endpoint
for i in {1..31}; do curl http://localhost:8000/api/digest/daily; done

# After 30th request, should get 429 Too Many Requests
```

---

## Database Schema

```sql
-- User signup table
CREATE TABLE user_joined (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL UNIQUE,
    token_expires_at DATETIME NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accessed_at DATETIME
);

-- Queries
SELECT COUNT(*) FROM user_joined;  -- How many joined?
SELECT * FROM user_joined WHERE accessed_at IS NOT NULL;  -- Who accessed?
```

---

## Deployment Checklist

- [ ] Add rate limiting to FastAPI
- [ ] Create UserJoined table
- [ ] Add /api/join-demo endpoint
- [ ] Add /api/validate-token endpoint
- [ ] Update config.py
- [ ] Create join-demo.html
- [ ] Update App.tsx with token validation
- [ ] Add slowapi to pyproject.toml
- [ ] Rebuild Docker
- [ ] Test full signup flow
- [ ] Test rate limiting
- [ ] Push to GitHub
- [ ] Create version2.0 tag

---

## Summary

**What users see:**
1. GitHub landing page (always available, safe)
2. Enter name/email
3. Get redirected to live TechLens (via ngrok)
4. App validates token automatically

**What attackers see:**
1. Rate-limited API (5 req/min for signup, 30 req/min for other endpoints)
2. GitHub landing page (GitHub's DDoS protection)
3. Can't brute force - token expires in 24 hours

**Security benefits:**
✅ Landing page not on public IP  
✅ Rate limiting protects backend  
✅ Token-based access control  
✅ User tracking (know who accessed)  
✅ Professional gatekeeping (looks intentional)

---

**Ready to implement? Should I start with Step 1?**
