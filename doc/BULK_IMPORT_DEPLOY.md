# Bulk Company CSV Import — Deploy Notes

The application code is shipped via the normal Django deploy. The ops
changes below are required ONCE on the EC2 box to support 10 GB CSV
uploads. Without them, nginx will reject the upload with 413 and
gunicorn will time out at 30 seconds.

## 1. Apply the migration

```bash
cd /home/ec2-user/FontEsin/fontesin-backend-django
source ../venv/bin/activate
python manage.py migrate accounts
```

If migrate complains about conflicting 0027 migrations (the prior
`0027_merge_20260515_1148` from a different branch and our new
`0027_companyimportjob`), generate a merge migration:

```bash
python manage.py makemigrations --merge
python manage.py migrate accounts
```

## 2. Raise nginx upload limit

Edit `/etc/nginx/conf.d/fontesin.conf` and bump `client_max_body_size`
plus the body/proxy timeouts:

```nginx
server {
    listen 80 default_server;
    server_name 54-183-170-147.nip.io 54.183.170.147 ...;

    client_max_body_size 10G;          # <— was 50M
    client_body_timeout 600s;          # <— new (10 min)
    proxy_read_timeout 600s;           # <— new (10 min)
    proxy_send_timeout 600s;           # <— new

    location /static/ { ... }
    location /media/  { ... }
    location / {
        proxy_pass http://127.0.0.1:8000;
        ...
    }
}
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 3. Raise gunicorn timeout

Edit `/etc/systemd/system/fontesin-gunicorn.service` and add
`--timeout 600` to the `ExecStart=` line. The default 30 s would
kill the upload phase for any file larger than ~150 MB on a
typical home connection.

```ini
ExecStart=/home/ec2-user/FontEsin/venv/bin/gunicorn \
    FontEsin.wsgi:application \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 600 \
    --access-logfile /home/ec2-user/FontEsin/fontesin-backend-django/logs/gunicorn-access.log \
    --error-logfile  /home/ec2-user/FontEsin/fontesin-backend-django/logs/gunicorn-error.log \
    --capture-output
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart fontesin-gunicorn
sudo systemctl status fontesin-gunicorn --no-pager
```

## 4. Create the imports directory

```bash
mkdir -p /home/ec2-user/FontEsin/fontesin-backend-django/imports
chmod 700 /home/ec2-user/FontEsin/fontesin-backend-django/imports
```

Files in this directory are server-generated UUIDs and are auto-deleted
on successful import. The matching `<uuid>.csv.errors.csv` is kept for
admin download until manually pruned.

## 5. Verify

1. Browse to `http://<host>/companies/` as a superuser
2. Confirm the new **"Import CSV"** button appears next to the tenant
   selector
3. Click it, download the sample CSV via the modal link
4. Upload that 3-row sample — the modal should show 3 inserted, 0 skipped
5. Re-upload the same file — should show 0 inserted, 3 skipped duplicates
6. Edit the sample with a bad row (unknown `tenant_slug`) — should show
   failed_rows > 0 and offer the errors.csv download

## 6. Scale-test before going to production volumes

The importer should sustain **>20k rows/sec** on a t3.small with the
shipped Postgres config. Validate before letting a 10M-row file loose:

```bash
# 100k synthetic rows. Target tenant is chosen at upload time in the UI,
# so the CSV itself doesn't reference a tenant.
python scripts/gen_test_csv.py --rows 100000 --out /tmp/100k.csv

# Then upload via the modal, picking the target tenant from the dropdown.
```

Then ramp to 1M, then 10M.

## 7. Roll back

If the deploy goes wrong:

```bash
# Roll back the migration
python manage.py migrate accounts 0026

# Revert the nginx + systemd changes via your config-management /
# previous-known-good copies.

# The CompanyImportJob table being dropped won't affect any other
# part of the app — the model is standalone.
```
