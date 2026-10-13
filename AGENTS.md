# Project working agreements

- After each code update, update the local production verification environment
  `netbox-access-relations-prod-verify` so the user can validate the latest changes
  at http://127.0.0.1:8001. Run appropriate checks, rebuild its dedicated production
  image, recreate the application and worker containers, and verify service health
  and that the running image contains the changes. Report any blocker explicitly.
- Use `docker-compose.prod.yml` with `.env.production.verify` and the explicit
  Compose project name `netbox-access-relations-prod-verify`. Never expose secrets
  from the environment file. Keep verification image tags separate from releases.
- Clean up confirmed obsolete project containers, images, and volumes after
  updates. Use exact resource names or IDs and check references before deleting.
  Preserve active resources, build dependencies, and persistent development or
  verification data. An unattached data volume is not automatically disposable.
  Never use global prune commands or delete unrelated project resources.
