# Polytope Containment Console — Operational Handoff

**Document Version**: 1.0.0  
**Last Updated**: 2026-08-24  
**Classification**: Internal Use Only

---

## 1. System Overview

The Polytope Containment Console is a safety-critical AI containment system that enforces ethical constraints on AI behavior through 14-dimensional geometric projection. This document provides operational guidance for administrators and operators.

### Key Capabilities

- **Real-time Safety Enforcement**: Verifies AI outputs against polytope constraints
- **Dual-Mode Operation**: Projection (corrects) or Refusal (rewrites/withholds)
- **Comprehensive Audit Trail**: Every decision logged with full traceability
- **Multi-Tenant Support**: API keys with per-client configuration
- **Government-Grade Security**: Rate limiting, lockout, CSRF protection, token revocation

### Security Features

| Feature | Configuration | Purpose |
|---------|---------------|---------|
| **MongoDB Connection** | `w="majority"`, `readConcern="majority"` | Data consistency |
| **Connection Pool** | 5-20 connections | High-throughput support |
| **Health Checks** | `/health`, `/readyz` | Load balancer support |
| **Security Headers** | CSP, X-Frame-Options, etc. | XSS/clickjacking protection |

---

## 2. Access Credentials

### Default Console Accounts

| Role | Email | Password | Access Level |
|------|-------|----------|--------------|
| Admin | `admin@polytope.console` | `Prussian#42Blue` | Full system access |
| Operator | `ops@polytope.console` | `Khaki#514Ops` | Gate, Chat, Simulator, read-only Constraints |

**⚠️ SECURITY REQUIREMENT**: Change these passwords immediately upon first login.

### Demo API Keys

Demo keys are generated randomly on each seed. Retrieve them from the database:

```bash
mongo DP3 --eval "db.clients.find({}, {name: 1, key_prefix: 1, active: 1}).pretty()"
```

**Note**: Full keys are only returned at creation/rotation time. They are not stored in plaintext.

---

## 3. System Architecture

### Components

```
Dimensions/
├── backend/                    # FastAPI application (port 8001)
│   ├── server.py              # Application bootstrap
│   ├── lib/                   # Core logic modules
│   ├── models/                # Pydantic schemas
│   ├── routers/               # API route handlers
│   ├── tests/                 # pytest test suite
│   └── seed.py                # Demo data generator
├── frontend/                   # React application (port 3000)
│   └── src/
│       ├── lib/               # API client, auth, types
│       └── components/        # UI components
└── memory/                     # Documentation
    ├── SPEC.md               # Detailed specification
    ├── EXECUTIVE_REVIEW.md   # Security audit
    └── HANDOFF.md           # This document
```

### External Dependencies

- **MongoDB Atlas**: Cloud database (connection in `.env`)
- **Supabase**: Optional hybrid auth (JWKS verification)
- **OpenAI-Compatible API**: Chat coach model (agnes-2.5-flash)

---

## 4. Daily Operations

### 4.1 Service Status Checks

```bash
# Check supervisor status
sudo supervisorctl status

# Expected output:
# backend        RUNNING   pid 1234, uptime 2:30:00
# frontend       RUNNING   pid 1235, uptime 2:30:00
```

### 4.2 Health Monitoring

```bash
# Backend health (detailed with database status)
curl -s http://localhost:8001/health | jq

# Frontend accessibility
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000

# Kubernetes-style readiness probe
curl -s http://localhost:8001/readyz
```

**Health Endpoint Response**:
```json
{
  "status": "healthy",
  "database": true,
  "uptime_seconds": 86400,
  "timestamp": "2026-08-24T12:00:00Z"
}
```

**Security Headers** (added by middleware):
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

### 4.3 Log Analysis

```bash
# Backend errors
tail -f /var/log/supervisor/backend.err.log

# Backend access
tail -f /var/log/supervisor/backend.out.log

# Frontend errors
tail -f /var/log/supervisor/frontend.err.log
```

### 4.4 Database Queries

```bash
# Connection to MongoDB
mongo "MONGO_URL" DP3

# Recent events
db.events.find().sort({created_at: -1}).limit(10)

# Locked accounts
db.account_lockouts.find()

# Active rate-limited IPs
db.login_attempts.aggregate([
  {$group: {_id: "$ip", count: {$sum: 1}}},
  {$sort: {count: -1}},
  {$limit: 10}
])
```

---

## 5. Administrative Procedures

### 5.1 User Management

**Via Console UI**:
1. Navigate to **Access** tab (admin only)
2. **Create User**: Enter email, password, select role
3. **Toggle Account**: Switch active/inactive
4. **Change Password**: Self-service via profile settings

**Via API**:
```bash
# List users
curl -H "Authorization: Bearer <token>" \
     http://localhost:8001/api/auth/users

# Create user (admin)
curl -X POST http://localhost:8001/api/auth/users \
     -H "Authorization: Bearer <token>" \
     -H "X-CSRF-Token: <csrf>" \
     -H "Content-Type: application/json" \
     -d '{"email": "new@example.com", "password": "Secure#Pass123", "role": "operator"}'
```

### 5.2 API Key Management

**Via Console UI**:
1. Navigate to **Clients** tab (admin only)
2. **Issue Key**: Enter name, description, optional profile pin
3. **Copy Key**: Shown once at creation — store securely
4. **Rotate Key**: Generates new key, invalidates old
5. **Revoke**: Deactivates client immediately

**Via API**:
```bash
# Create client
curl -X POST http://localhost:8001/api/clients \
     -H "Authorization: Bearer <token>" \
     -H "X-CSRF-Token: <csrf>" \
     -H "Content-Type: application/json" \
     -d '{"name": "Production App", "description": "Main integration", "profile_id": "prof-biochem-strict"}'

# Rotate key
curl -X POST http://localhost:8001/api/clients/<id>/rotate \
     -H "Authorization: Bearer <token>" \
     -H "X-CSRF-Token: <csrf>"
```

### 5.3 Profile Management

**Activate Profile**:
```bash
curl -X POST http://localhost:8001/api/profiles/<id>/activate \
     -H "Authorization: Bearer <token>" \
     -H "X-CSRF-Token: <csrf>"
```

**View Margins**:
```bash
curl http://localhost:8001/api/profiles/<id>/margins \
     -H "Authorization: Bearer <token>"
```

### 5.4 Emergency Procedures

**Lock Compromised Account**:
```bash
# Via UI: Access tab → toggle off
# Or directly:
mongo "MONGO_URL" DP3 --eval '
  db.users.updateOne(
    {email: "compromised@example.com"},
    {$set: {active: false}}
  )
'
```

**Clear Rate Limits**:
```bash
mongo "MONGO_URL" DP3 --eval '
  db.login_attempts.deleteMany({ip: "attacker-ip"})
  db.account_lockouts.deleteMany({email: "target@example.com"})
'
```

**Revoke All Tokens**:
```bash
mongo "MONGO_URL" DP3 --eval '
  db.jwt_denylist.deleteMany({})
'
# Notify users to re-authenticate
```

---

## 6. Security Monitoring

### 6.1 Failed Login Monitoring

```bash
# Count failed attempts in last hour
mongo "MONGO_URL" DP3 --eval '
  db.login_attempts.countDocuments({
    timestamp: {$gte: new Date(Date.now() - 3600000)}
  })
'

# Top offending IPs
mongo "MONGO_URL" DP3 --eval '
  db.login_attempts.aggregate([
    {$match: {timestamp: {$gte: new Date(Date.now() - 3600000)}}},
    {$group: {_id: "$ip", count: {$sum: 1}}},
    {$sort: {count: -1}},
    {$limit: 10}
  ])
'
```

### 6.2 Locked Accounts

```bash
mongo "MONGO_URL" DP3 --eval '
  db.account_lockouts.find({}, {email: 1, locked_at: 1, expires_at: 1}).pretty()
'
```

### 6.3 Revoked Tokens

```bash
mongo "MONGO_URL" DP3 --eval '
  db.jwt_denylist.countDocuments()
'
```

### 6.4 Security Events

Monitor for:
- Multiple failed logins from same IP
- Accounts hitting lockout threshold
- Unusual API key usage patterns
- High violation rates on specific profiles

---

## 7. Maintenance Tasks

### 7.1 Regular Maintenance

**Daily**:
- [ ] Check service status
- [ ] Review error logs
- [ ] Monitor active lockouts

**Weekly**:
- [ ] Review audit log for anomalies
- [ ] Check database growth rates
- [ ] Verify backup integrity

**Monthly**:
- [ ] Rotate admin passwords
- [ ] Review API key usage
- [ ] Clean old audit logs

### 7.2 Database Cleanup

```bash
# Clean old login attempts (>24h)
mongo "MONGO_URL" DP3 --eval '
  db.login_attempts.deleteMany({
    timestamp: {$lt: new Date(Date.now() - 86400000)}
  })
'

# Clean expired account lockouts
mongo "MONGO_URL" DP3 --eval '
  db.account_lockouts.deleteMany({
    expires_at: {$lt: new Date()}
  })
'

# Clean expired CSRF tokens
mongo "MONGO_URL" DP3 --eval '
  db.csrf_tokens.deleteMany({
    expires_at: {$lt: new Date()}
  })
'

# Clean expired nonces
mongo "MONGO_URL" DP3 --eval '
  db.auth_nonces.deleteMany({
    expires_at: {$lt: new Date()}
  })
'
```

### 7.3 Log Rotation

Configure logrotate for supervisor logs:
```bash
sudo nano /etc/logrotate.d/polytope
```

```
/var/log/supervisor/backend*.log
/var/log/supervisor/frontend*.log {
    weekly
    rotate 12
    compress
    missingok
    notifempty
    copytruncate
}
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Backend won't start**:
```bash
# Check syntax
cd backend && python -m py_compile server.py

# Check environment
cat .env | grep JWT_SECRET

# View logs
tail -f /var/log/supervisor/backend.err.log
```

**Frontend shows blank page**:
```bash
# Check type errors
cd frontend && pnpm typecheck

# Check browser console
# F12 → Console tab
```

**MongoDB connection fails**:
```bash
# Test connection
mongo "MONGO_URL" --eval "db.adminCommand('ping')"

# Check network
nc -zv ac-djukaxv-shard-00-00.n9ousvq.mongodb.net 27017
```

**Rate limiting too aggressive**:
```bash
# Check current limits
mongo "MONGO_URL" DP3 --eval "db.settings.findOne()"

# Adjust if needed (requires restart)
# Update EngineSettings.rate_limit_default_per_min
```

### 8.2 Performance Issues

**Slow queries**:
```bash
# Check indexes
mongo "MONGO_URL" DP3 --eval "db.events.getIndexes()"

# Add missing indexes
db.events.createIndex({created_at: -1})
db.events.createIndex({profile_id: 1, created_at: -1})
```

**High memory usage**:
```bash
# Check collection sizes
mongo "MONGO_URL" DP3 --eval "
  db.getCollectionNames().forEach(function(c) {
    var s = db.getCollection(c).stats();
    print(c + ': ' + Math.round(s.size / 1024 / 1024) + ' MB');
  })
"
```

---

## 9. Deployment Checklist

### Pre-Production

- [ ] All default passwords changed
- [ ] JWT_SECRET rotated to secure value
- [ ] MongoDB connection uses TLS
- [ ] CORS origins restricted to production domain
- [ ] Rate limits tuned for expected load
- [ ] Backup strategy verified
- [ ] Monitoring/alerting configured
- [ ] Incident response plan documented

### Post-Deployment

- [ ] Security scan completed
- [ ] Penetration test performed
- [ ] Performance benchmarks established
- [ ] Operational runbook distributed
- [ ] On-call rotation established

---

## 10. Contact Information

| Role | Contact |
|------|---------|
| System Administrator | security@smartscott.com |
| Security Issues | Report privately via GitHub Security Advisory |
| Commercial Licensing | licensing@smartscott.com |

---

## 11. Document Control

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-08-24 | Initial release |
| 1.1.0 | 2026-08-24 | Added health checks, MongoDB security, CSP headers (42 tests passing) |

---

**End of Document**
