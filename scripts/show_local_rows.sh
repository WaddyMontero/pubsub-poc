#!/usr/bin/env sh
set -eu

docker compose exec postgres psql -U poc -d poc -c \
  "select event_id, vendor_record_id, customer_name, status, extracted_at from landing_records order by extracted_at desc limit 10;"
