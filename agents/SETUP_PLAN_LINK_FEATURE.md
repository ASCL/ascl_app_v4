# ASCL Link Feature - Setup and Implementation Plan

**Date Created:** 2025-11-11
**Feature:** Add ability to associate typed links to ASCL code entries

---

## Overview

This plan outlines how to:
1. Stand up a local development instance of the ASCL PHP application
2. Add a new feature to associate links (with link types) to code entries
3. Test the changes before deploying to production

**Key Points:**
- ✅ Can be done without WordPress
- ✅ Can be done without upgrading CodeIgniter (not recommended to upgrade)
- ✅ Database changes will be needed (2 new tables)
- ✅ PHP code changes are straightforward

---

## Part 1: Local Development Setup

### Step 1: Configure MySQL Database

**1.1 Connect to MySQL on port 3307:**
```bash
mysql -h localhost -P 3307 -u root -p
```

**1.2 Create the database (if it doesn't exist):**
```sql
CREATE DATABASE IF NOT EXISTS ascl_db CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci;
```

**1.3 Create a database user:**
```sql
CREATE USER 'ascl_db'@'localhost' IDENTIFIED BY 'your_secure_password_here';
GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_db'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

**1.4 Import the database schema:**
```bash
mysql -h localhost -P 3307 -u ascl_db -p ascl_db < /home/demitri/repositories/ASCL/ascl_php_application/ascl_db-schema-2025-10-30.sql
```

**1.5 Verify tables were created:**
```bash
mysql -h localhost -P 3307 -u ascl_db -p ascl_db -e "SHOW TABLES;"
```

### Step 2: Configure PHP Application

**2.1 Update database configuration:**

Edit: `/home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application/application/config/database.php`

Change line 51:
```php
$db['default']['hostname'] = 'localhost:3307';  // Add :3307 for the port
```

Update credentials (lines 52-53):
```php
$db['default']['username'] = 'ascl_db';
$db['default']['password'] = 'your_secure_password_here';  // Match what you set above
```

**2.2 Update application configuration:**

Edit: `/home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application/application/config/config.php`

Change line 17 to use local URL:
```php
$config['base_url'] = 'http://localhost:8080/';
```

**2.3 Set file permissions:**
```bash
cd /home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application
chmod -R 775 application/cache application/logs
```

### Step 3: Configure nginx

**3.1 Create nginx configuration file:**

Create: `/etc/nginx/sites-available/ascl-local.conf`

```nginx
server {
    listen 8080;
    server_name localhost;

    root /home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application;
    index index.php index.html;

    # Logging
    access_log /var/log/nginx/ascl-local-access.log;
    error_log /var/log/nginx/ascl-local-error.log;

    # Remove index.php from URLs
    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    # PHP handling
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php7.4-fpm.sock;  # Adjust if needed
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
    }

    # Deny access to application and system directories
    location ~ ^/(application|system)/ {
        deny all;
    }
}
```

**3.2 Enable the site:**
```bash
sudo ln -s /etc/nginx/sites-available/ascl-local.conf /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

**3.3 Verify PHP-FPM is running:**
```bash
sudo systemctl status php7.4-fpm
# If not running:
sudo systemctl start php7.4-fpm
```

### Step 4: Test Basic Setup

**4.1 Test the homepage:**
```bash
curl http://localhost:8080/
```

**4.2 Access in browser:**
Open: http://localhost:8080/

You should see the ASCL homepage (may have errors about WordPress content - that's OK).

**4.3 Check if database connection works:**
Try browsing codes: http://localhost:8080/code/all

---

## Part 2: Database Changes for Link Feature

### Step 1: Create Link Types Table

```sql
CREATE TABLE `link_types` (
  `id` int NOT NULL AUTO_INCREMENT,
  `type_name` varchar(100) NOT NULL,
  `display_order` int DEFAULT 0,
  `description` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `type_name` (`type_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### Step 2: Create Code Links Table

```sql
CREATE TABLE `code_links` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code_id` int NOT NULL,
  `link_url` varchar(500) NOT NULL,
  `link_type_id` int NOT NULL,
  `link_text` varchar(255) DEFAULT NULL COMMENT 'Optional display text for the link',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `code_id` (`code_id`),
  KEY `link_type_id` (`link_type_id`),
  FOREIGN KEY (`code_id`) REFERENCES `codes` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`link_type_id`) REFERENCES `link_types` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### Step 3: Populate Initial Link Types

```sql
INSERT INTO `link_types` (`type_name`, `display_order`, `description`) VALUES
('Documentation', 1, 'Official documentation or user guide'),
('Tutorial', 2, 'Tutorial or how-to guide'),
('GitHub Repository', 3, 'GitHub repository link'),
('GitLab Repository', 4, 'GitLab repository link'),
('Bitbucket Repository', 5, 'Bitbucket repository link'),
('Paper/Publication', 6, 'Related academic paper or publication'),
('Video', 7, 'Video tutorial or presentation'),
('Example/Demo', 8, 'Example implementation or demo'),
('Docker Image', 9, 'Docker container image'),
('Package Manager', 10, 'PyPI, CRAN, npm, etc.'),
('Related Project', 11, 'Related software project'),
('Other', 99, 'Other type of link');
```

### Step 4: Verify Tables

```sql
-- Check link_types
SELECT * FROM link_types ORDER BY display_order;

-- Check code_links structure
DESCRIBE code_links;

-- Test adding a sample link (using code_id = 1 if it exists)
-- This is just for testing - you can delete it later
INSERT INTO code_links (code_id, link_url, link_type_id, link_text)
VALUES (1, 'https://example.com/docs', 1, 'Example Documentation');

-- Verify the insert
SELECT cl.*, lt.type_name
FROM code_links cl
JOIN link_types lt ON cl.link_type_id = lt.id
WHERE cl.code_id = 1;
```

---

## Part 3: Code Changes Overview

### Files to Modify:

1. **Admin Form Template** - Add link management interface
   - File: `application/views/adm_insert_update_code.php`
   - Add: Form fields for managing links (URL, type dropdown, text)

2. **Admin Controller** - Handle form submission
   - File: `application/controllers/adm.php`
   - Modify: `update_code()` method (line 64+)
   - Add: Code to save/update/delete links

3. **Code Display Template** - Show links on code page
   - File: `application/views/template/codelist.php`
   - Modify: Lines 56-82 (the section that displays sites/references)
   - Add: Section to display associated links grouped by type

4. **Helper Functions** - Add link retrieval function
   - File: `application/helpers/ascl_helper.php`
   - Add: `get_code_links($code_id)` function

### Implementation Notes:

**For the admin form:**
- Add JavaScript to allow adding multiple links dynamically
- Each link row has: URL input, type dropdown, optional text input, delete button
- Links stored in a hidden field or as form array for submission

**For the controller:**
- On form submit, delete existing links for the code
- Re-insert all links from the form (simple approach)
- Validate URLs and link types

**For display:**
- Group links by type
- Show type name as heading
- Show links with optional custom text or just URL

---

## Part 4: Testing Plan

### Phase 1: Verify Setup
1. ✅ Can access http://localhost:8080/
2. ✅ Can browse codes at /code/all
3. ✅ Database tables created
4. ✅ Sample data in link_types

### Phase 2: Test Admin Interface
1. Login to admin (need to create admin user if none exists)
2. Navigate to edit a code entry
3. See new link management section
4. Add 2-3 test links with different types
5. Save and verify no errors

### Phase 3: Test Display
1. View the code entry you just edited
2. Verify links appear in correct section
3. Verify links grouped by type
4. Verify links are clickable
5. Test with code that has no links (should show nothing)

### Phase 4: Edge Cases
1. Test with very long URLs
2. Test with special characters in URLs
3. Test with empty link text
4. Test deleting all links from a code
5. Test with maximum number of links (10+)

---

## Part 5: Creating an Admin User (If Needed)

If you need to create an admin user for testing:

```sql
-- Check if users table has any users
SELECT * FROM users;

-- If empty, create a test admin user
-- Password is SHA1 hash of 'testpassword123' - CHANGE THIS!
INSERT INTO users (username, real_name, password, login_attempts)
VALUES ('admin', 'Test Admin', SHA1('testpassword123'), 0);

-- Verify
SELECT id, username, real_name FROM users;
```

**Login URL:** http://localhost:8080/adm

**IMPORTANT:** Change the password immediately after testing!

---

## Part 6: Sample Test Data

Once setup is complete, you can test with this sample data:

```sql
-- Get a code ID to work with
SELECT id, ascl_id, title FROM codes LIMIT 5;

-- Add sample links (replace code_id = 1 with actual ID)
INSERT INTO code_links (code_id, link_url, link_type_id, link_text) VALUES
(1, 'https://github.com/example/repo', 3, 'Source Code Repository'),
(1, 'https://example.com/docs', 1, 'Official Documentation'),
(1, 'https://youtube.com/watch?v=example', 7, 'Tutorial Video'),
(1, 'https://arxiv.org/abs/example', 6, 'Method Paper');

-- View the links
SELECT
    c.ascl_id,
    c.title,
    lt.type_name,
    cl.link_url,
    cl.link_text
FROM code_links cl
JOIN codes c ON cl.code_id = c.id
JOIN link_types lt ON cl.link_type_id = lt.id
WHERE c.id = 1
ORDER BY lt.display_order;
```

---

## Part 7: Rollback Plan

If something goes wrong:

**Rollback database changes:**
```sql
DROP TABLE IF EXISTS code_links;
DROP TABLE IF EXISTS link_types;
```

**Restore original files:**
```bash
cd /home/demitri/repositories/ASCL/ascl_php_application
git status  # Check what was modified
git checkout -- <file>  # Restore individual files
# OR
git reset --hard  # Restore all files (loses all changes!)
```

**Disable nginx site:**
```bash
sudo rm /etc/nginx/sites-enabled/ascl-local.conf
sudo systemctl reload nginx
```

---

## Part 8: Next Steps After This Session

When you return to implement:

1. **Start with Part 1** - Get the local environment running
2. **Then Part 2** - Create database tables
3. **Test access** - Make sure you can view existing codes
4. **Contact me** - I'll provide the specific PHP code changes for Part 3

---

## Questions to Answer Before Coding:

1. **Link display location:** Where on the code page should links appear?
   - With existing "Code site" / "Described in" / "Used in" section?
   - In a separate section below?

2. **Admin interface:** Should link management be:
   - Inline on the main edit form?
   - A separate "Manage Links" page?

3. **Link limits:** Should there be a maximum number of links per code?

4. **Link validation:** Should we validate that URLs are accessible before saving?

5. **Link types:** Are the suggested types in Step 3 of Part 2 sufficient?

---

## Files Reference

**Key Files:**
```
/home/demitri/repositories/ASCL/ascl_php_application/
├── ascl_db-schema-2025-10-30.sql          # Original schema
├── web_root/ascl_php_application/
    ├── index.php                           # Entry point
    ├── .htaccess                          # URL rewriting
    ├── application/
    │   ├── config/
    │   │   ├── config.php                 # Base URL, session config
    │   │   ├── database.php               # DB connection settings
    │   │   └── routes.php                 # URL routing
    │   ├── controllers/
    │   │   ├── adm.php                    # Admin controller (TO MODIFY)
    │   │   └── code.php                   # Code viewing controller
    │   ├── views/
    │   │   ├── adm_insert_update_code.php # Admin form (TO MODIFY)
    │   │   ├── code_view.php              # Individual code view
    │   │   └── template/
    │   │       └── codelist.php           # Code display template (TO MODIFY)
    │   └── helpers/
    │       └── ascl_helper.php            # Helper functions (TO MODIFY)
```

**CodeIgniter Version:** 2.1.4 (very old, but don't upgrade)
**PHP Version:** 7.4.33
**MySQL Version:** 5.7.24

---

## Security Notes

- The admin password is stored as SHA1 (weak) - don't use production passwords
- This is a local development environment only
- Don't expose port 8080 to the internet
- Keep database credentials secure
- The production site uses different security measures

---

## Troubleshooting

**"Access denied" database error:**
- Check hostname includes port: `localhost:3307`
- Verify credentials match what you set
- Ensure user has privileges: `SHOW GRANTS FOR 'ascl_db'@'localhost';`

**nginx 404 errors:**
- Check document root path is correct
- Verify file permissions: `ls -la web_root/ascl_php_application/`
- Check nginx error log: `sudo tail -f /var/log/nginx/ascl-local-error.log`

**PHP errors:**
- Enable error display in `index.php`: Ensure `ENVIRONMENT` is set to `'development'`
- Check PHP-FPM log: `sudo tail -f /var/log/php7.4-fpm.log`

**"Can't connect to MySQL server" on port 3307:**
```bash
# Check if MySQL is running on 3307
sudo netstat -tlnp | grep 3307
# OR
sudo ss -tlnp | grep 3307
```

---

## Estimated Time

- **Part 1 (Setup):** 1-2 hours
- **Part 2 (Database):** 15 minutes
- **Part 3 (Code changes):** 2-4 hours (with guidance)
- **Part 4 (Testing):** 1 hour

**Total:** 4-7 hours depending on familiarity with tools

---

## Contact Points for Next Session

When you return, we'll need to:
1. ✅ Verify setup is working
2. ✅ Answer the design questions in Part 8
3. ✅ Write the PHP code for Part 3
4. ✅ Test thoroughly
5. ✅ Document for production deployment

**Save this file!** It contains everything needed to resume work.
