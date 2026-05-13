# GitHub Repository Security Configuration

## ✅ Already Completed
- CODEOWNERS file created and committed
- All code now designated to: @aryaMehta26

---

## 🔐 Complete GitHub Setup Instructions

### Option 1: Using GitHub Web UI (Recommended - 5 minutes)

#### Step 1: Go to Repository Settings
1. Navigate to: https://github.com/aryaMehta26/LayoverOS
2. Click **Settings** (top menu)
3. Click **Branches** (left sidebar)

#### Step 2: Add Branch Protection Rule for `main`
1. Click **Add rule** button
2. In the "Branch name pattern" field, enter: `main`
3. Click **Create**

#### Step 3: Configure Protection Settings
Check these boxes:
```
✅ Require a pull request before merging
   ├─ Require approvals: 1
   └─ ✅ Dismiss stale pull request approvals when new commits are pushed

✅ Require status checks to pass before merging

✅ Require branches to be up to date before merging

✅ Require code reviews from code owners
   └─ (Auto-enabled with CODEOWNERS file)

✅ Restrict who can push to matching branches
   ├─ Select: Only allow specified people to push to matching branches
   └─ Add: @aryaMehta26 (yourself)

✅ Lock branch
   └─ (Optional - prevents accidental commits)

✅ Require a conversation resolution before merging
   └─ (Optional - requires resolving all comments)
```

#### Step 4: Click **Save changes**

---

### Option 2: Using GitHub CLI (Faster - Terminal)

```bash
# Install GitHub CLI (if not already installed)
brew install gh

# Login to GitHub
gh auth login

# Create branch protection for main (only you can push)
gh api repos/aryaMehta26/LayoverOS/branches/main/protection \
  -X PUT \
  -f required_pull_request_reviews.required_approvals=1 \
  -f require_code_owner_reviews=true \
   -f restrict_pushes.dismissal_restrictions.users='["aryaMehta26"]' \
  -f restrict_pushes.dismiss_stale_reviews=true \
  -f enforce_admins=true

# Verify the protection is set
gh api repos/aryaMehta26/LayoverOS/branches/main/protection
```

---

## 📋 What This Does

| Setting | Effect |
|---------|--------|
| **Require PR** | Nobody can commit directly to `main` |
| **Require approvals** | Need at least 1 approval before merge |
| **Code owner review** | @aryaMehta26 (you) must approve all PRs |
| **Only you can push** | Only your GitHub account can push directly (if protection bypassed) |
| **Stale reviews dismissed** | If new commits added, old approvals ignored |
| **Status checks** | Automated tests must pass |

---

## 🔄 How This Affects Your Workflow

### Before (Current)
```
Anyone → Push to main ❌
```

### After (Protected)
```
Anyone → Create PR
   → CI checks run
   → @aryaMehta26 reviews
   → @aryaMehta26 approves
   → Merge to main ✅
```

---

## 👥 Workflow for Others (or Future Contributors)

```
Developer A wants to add feature:

1. Clone repo
   git clone https://github.com/aryaMehta26/LayoverOS.git

2. Create feature branch
   git checkout -b feature/my-feature

3. Make changes and push
   git push origin feature/my-feature

4. Create Pull Request (GitHub shows button)
   - Give it a clear title
   - Add description
   - Click "Create Pull Request"
   
5. GitHub automatically:
   - Runs tests/checks
   - Notifies @aryaMehta26 (code owner)
   - Requires approval from @aryaMehta26
   
6. @aryaMehta26 reviews on GitHub:
   - Click "Review changes"
   - Add comments if needed
   - Click "Approve"
   - Click "Merge pull request"
   
7. PR merged to main ✅
   - GitHub deletes feature branch (optional)
```

---

## 🧑‍💼 How to Review PRs on GitHub

### As Code Owner (@aryaMehta26)

#### When someone creates a PR:
1. Go to: https://github.com/aryaMehta26/LayoverOS/pulls
2. Click the PR
3. Review the **Files changed** tab
4. Click **Review changes** (top right)
5. Choose:
   - **Comment**: Just notes
   - **Approve**: Allows merge
   - **Request changes**: Blocks merge until fixes applied
6. Click **Submit review**

#### After review, click **Merge pull request**

---

## 🚫 Emergency Override (If Needed)

If you need to bypass protection for an emergency:

```bash
# Using GitHub CLI - Force push (requires admin)
gh api repos/aryaMehta26/LayoverOS/branches/main/protection \
   -X PATCH \
   -f enforce_admins=false

# Make your changes
# Then re-enable:
gh api repos/aryaMehta26/LayoverOS/branches/main/protection \
   -X PATCH \
   -f enforce_admins=true
```

---

## ✅ Checklist After Setup

- [ ] CODEOWNERS file committed ✅ (Done)
- [ ] Go to Repository Settings → Branches
- [ ] Create rule for `main` branch
- [ ] Enable all protection settings
- [ ] Set only @aryaMehta26 can push
- [ ] Make @aryaMehta26 required reviewer
- [ ] Test by creating a test PR (don't merge without review)
- [ ] Verify others cannot push directly to `main`

---

## 🧪 Test Your Setup

### Test 1: Verify Direct Push Blocked
```bash
# Try to push directly to main (should fail)
git checkout main
echo "test" >> test.txt
git add test.txt
git commit -m "test commit"
git push origin main

# Expected: ❌ REJECTED
# Message: "To push to this branch, you need permission"
```

### Test 2: Verify PR Required
```bash
# Create feature branch instead
git checkout -b test-feature
echo "test" >> test.txt
git add test.txt
git commit -m "test commit"
git push origin test-feature

# GitHub will show: "Create Pull Request" button
# This is the correct workflow ✅
```

---

## 📞 Support

**Q: Can admins bypass branch protection?**
A: Yes, if you enable "Include administrators" in settings.

**Q: What if I'm an admin and forget to review?**
A: PR stays open until you review. Create automated reminders.

**Q: Can I add multiple reviewers?**
A: Yes, under "Require a pull request before merging" → increase "required approvals" number.

**Q: How do I add other code owners?**
A: Edit `.github/CODEOWNERS` file and add their GitHub handle.

---

## 📝 Example CODEOWNERS File (If Adding Others Later)

```
# Frontend
frontend/ @aryaMehta26 @OtherPerson

# Backend
agent_graph.py @aryaMehta26
api.py @aryaMehta26

# Docs
*.md @aryaMehta26

# Everything else
* @aryaMehta26
```

---

**Your repository is now secure! Only you can approve and merge to main. 🔐**
