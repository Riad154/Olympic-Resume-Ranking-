# GitHub Actions Secrets Setup

Add these 7 secrets at:  
**https://github.com/Riad154/Olympic-Resume-Ranking-/settings/secrets/actions**

---

## Secret 1
**Name:** `BDJOBS_USER`

**Value:**
```
olympicbd
```

---

## Secret 2
**Name:** `BDJOBS_PASS`

**Value:**
```
machang*
```

---

## Secret 3
**Name:** `PG_HOST`

**Value:**
```
ep-spring-sea-ao46loy5-pooler.c-2.ap-southeast-1.aws.neon.tech
```

---

## Secret 4
**Name:** `PG_PORT`

**Value:**
```
5432
```

---

## Secret 5
**Name:** `PG_DBNAME`

**Value:**
```
neondb
```

---

## Secret 6
**Name:** `PG_USER`

**Value:**
```
neondb_owner
```

---

## Secret 7
**Name:** `PG_PASSWORD`

**Value:**
```
npg_XLFcpsC1V3rk
```

---

## Steps

1. Go to **GitHub repo → Settings → Secrets and variables → Actions**
2. Click **"New repository secret"**
3. Copy-paste each **Name** and **Value** from above
4. Click **Add secret**
5. Repeat for all 7 secrets
6. Go to **Actions** tab and re-run the failed workflow

## Next Step

After adding all secrets, re-trigger the BDJobs scraper workflow and share the new logs.
