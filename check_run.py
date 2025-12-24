from app import app, db
from webapp.models import EnrichmentRun, Practice
import json

with app.app_context():
    run = EnrichmentRun.query.get(6)
    if run:
        print('=== Run 6 Details ===')
        print(f'Status: {run.status}')
        print(f'Total: {run.total_practices}')
        print(f'Successful: {run.successful}')
        print(f'Failed: {run.failed}')
        print(f'Skipped: {run.skipped}')
        print(f'Started: {run.started_at}')
        print(f'Completed: {run.completed_at}')
        print(f'Success Rate: {run.success_rate}%')
        print(f'Total Cost: ${run.total_cost}')
        print(f'Config: {json.dumps(run.config, indent=2)}')
        print()

        # Check one of the enriched practices
        enriched = Practice.query.filter_by(enrichment_run_id=6).first()
        if enriched:
            print(f'=== Sample Enriched Practice ===')
            print(f'Name: {enriched.practice_name}')
            print(f'Status: {enriched.enrichment_status}')
            print(f'Enriched At: {enriched.enriched_at}')
            if enriched.data:
                print(f'Data fields: {len(enriched.data)}')
                print(f'Sample fields:')
                for key in list(enriched.data.keys())[:10]:
                    val = enriched.data[key]
                    if isinstance(val, str) and len(val) > 100:
                        val = val[:100] + '...'
                    print(f'  {key}: {val}')
    else:
        print('Run 6 not found')
