"""Separate the development database from the existing student deployment."""


def resolve_spreadsheet_id(secrets, environment='production'):
    if environment == 'production':
        identifier = str(secrets.get('spreadsheet_id', '')).strip()
        if not identifier:
            raise ValueError('The student database has not been configured.')
        return identifier
    if environment != 'staging':
        raise ValueError('Unknown deployment environment; database access is stopped.')
    testing = str(secrets.get('staging_spreadsheet_id', '')).strip()
    production = str(secrets.get('production_spreadsheet_id', '')).strip()
    existing = str(secrets.get('spreadsheet_id', '')).strip()
    if not testing or not production:
        raise ValueError('Staging requires an independent test database and the production database identifier.')
    if testing == production or (existing and testing == existing):
        raise ValueError('Staging must not use the student database. No database was opened.')
    return testing
