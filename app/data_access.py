import mariadb
from os import path
from .models import MikeRecord, CountryRecord, MikeRecordProvider, CountryRecordProvider, MasterPasswordProvider, \
    DataAccessError, InvalidPrimaryKeyOperationError, NoMasterPasswordError
from typing import Iterable, Optional
from argon2 import PasswordHasher


class MariaDBRecordProvider(MikeRecordProvider, CountryRecordProvider):
    def __init__(self, config: dict) -> None:
        self.pool = mariadb.ConnectionPool(host=config['DB_HOST'],
                                           port=config['DB_PORT'],
                                           user=config['DB_USER'],
                                           password=config['DB_PASSWORD'],
                                           database=config['DB_NAME'],
                                           pool_name='all-ears',
                                           pool_size=20)

    # Implements MikeRecordProvider

    def add_mike_record(self, record: MikeRecord):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                self._add_record(cur, record)
                conn.commit()
            except (mariadb.IntegrityError, mariadb.Error) as e:
                conn.rollback()
                if isinstance(e, mariadb.IntegrityError):
                    raise InvalidPrimaryKeyOperationError(record)
                else:
                    raise DataAccessError()

    def add_mike_records(self, records: Iterable[MikeRecord]):
        curr_record = None
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                for record in records:
                    curr_record = record
                    self._add_record(cur, record)
                conn.commit()
            except (mariadb.IntegrityError, mariadb.Error) as e:
                conn.rollback()
                if isinstance(e, mariadb.IntegrityError):
                    raise InvalidPrimaryKeyOperationError(curr_record)
                else:
                    raise DataAccessError()

    def add_or_overwrite_mike_records(self, records: Iterable[MikeRecord]):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                for record in records:
                    cur.execute('replace into elephantcarcasses '
                                '( un_region'
                                ', subregion_name'
                                ', subregion_id'
                                ', country_name'
                                ', country_code'
                                ', mike_site_id'
                                ', mike_site_name'
                                ', mike_year'
                                ', carcasses'
                                ', illegal_carcasses ) '
                                'values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', record.to_tuple())
                conn.commit()
            except mariadb.Error:
                conn.rollback()
                raise DataAccessError()

    @staticmethod
    def _add_record(cursor, record: MikeRecord):
        cursor.execute('insert into elephantcarcasses '
                       '( un_region'
                       ', subregion_name'
                       ', subregion_id'
                       ', country_name'
                       ', country_code'
                       ', mike_site_id'
                       ', mike_site_name'
                       ', mike_year'
                       ', carcasses'
                       ', illegal_carcasses ) '
                       'values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', record.to_tuple())

    def get_mike_record(self, record_key: MikeRecord.PrimaryKey) -> Optional[MikeRecord]:
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('select '
                            'un_region'
                            ', subregion_name'
                            ', subregion_id'
                            ', country_name'
                            ', country_code'
                            ', mike_site_id'
                            ', mike_site_name'
                            ', mike_year'
                            ', carcasses'
                            ', illegal_carcasses '
                            'from elephantcarcasses '
                            'where mike_site_id = ? and mike_year = ?', record_key)
            except mariadb.Error:
                raise DataAccessError()
            if cur.fieldcount() == 0:
                return None
            else:
                return MikeRecord.from_tuple(cur.fetchone())

    def get_all_mike_records(self) -> Iterable[MikeRecord]:
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('select * from elephantcarcasses')
            except mariadb.Error:
                raise DataAccessError()
            if cur.fieldcount() == 0:
                return []
            else:
                return list(map(MikeRecord.from_tuple, cur))

    def update_mike_record(self, record: MikeRecord):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                self._update_record(cur, record)
                conn.commit()
            except mariadb.Error:
                conn.rollback()
                raise DataAccessError()

    def update_mike_records(self, records: Iterable[MikeRecord]):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                for record in records:
                    self._update_record(cur, record)
                conn.commit()
            except mariadb.Error:
                conn.rollback()
                raise DataAccessError()

    @staticmethod
    def _update_record(cursor, record: MikeRecord):
        record_tup = record.to_tuple()
        cursor.execute('update elephantcarcasses set'
                       ' un_region = ?'
                       ', subregion_name = ?'
                       ', subregion_id = ?'
                       ', country_name = ?'
                       ', country_code = ?'
                       ', mike_site_name = ?'
                       ', carcasses = ?'
                       ', illegal_carcasses = ?  '
                       'where mike_site_id = ? and mike_year = ?',
                       record_tup[0:5] + (record_tup[6],) + record_tup[7:] + record.get_primary_key())

    def remove_mike_record(self, record_key: MikeRecord.PrimaryKey):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                self._remove_record(cur, record_key)
                conn.commit()
            except mariadb.Error:
                conn.rollback()
                raise DataAccessError()

    def remove_mike_records(self, record_keys: Iterable[MikeRecord.PrimaryKey]):
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                for record_key in record_keys:
                    self._remove_record(cur, record_key)
                conn.commit()
            except mariadb.Error:
                conn.rollback()
                raise DataAccessError()

    @staticmethod
    def _remove_record(cursor, record_key: MikeRecord.PrimaryKey):
        cursor.execute('delete from elephantcarcasses '
                       'where mike_site_id = ? and mike_year = ?',
                       record_key)

    # Implements CountryRecordProvider

    def get_country_record(self, record_key: CountryRecord.PrimaryKey) -> Optional[CountryRecord]:
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('select '
                            'country_name'
                            ', country_code'
                            ', mike_year'
                            ', count(carcasses) as carcasses'
                            ', count(illegal_carcasses) as illegal_carcasses '
                            'from elephantcarcasses '
                            'where country_code = ? and mike_year = ? '
                            'group by country_code, mike_year', record_key)
            except mariadb.Error:
                raise DataAccessError()
            if cur.fieldcount() == 0:
                return None
            else:
                return CountryRecord.from_tuple(cur.fetchone())

    def get_all_country_records(self) -> Iterable[CountryRecord]:
        with self.pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('select '
                            'country_name'
                            ', country_code'
                            ', mike_year'
                            ', count(carcasses) as carcasses'
                            ', count(illegal_carcasses) as illegal_carcasses '
                            'from elephantcarcasses '
                            'group by country_code, mike_year')
            except mariadb.Error:
                raise DataAccessError()
            if cur.fieldcount() == 0:
                return []
            else:
                return list(map(lambda x: CountryRecord.from_tuple(x), cur))


class TextFileMasterPasswordProvider(MasterPasswordProvider):
    def __init__(self, instance_folder: str) -> None:
        self.master_pwd_file = path.join(instance_folder, 'password.txt')

    def verify_pwd(self, plain_pwd: str) -> bool:
        if path.isfile(self.master_pwd_file):
            try:
                with open(self.master_pwd_file, 'r') as f:
                    master_pwd_hash = f.read()
                    if master_pwd_hash == '':
                        raise NoMasterPasswordError()
                    else:
                        return PasswordHasher().verify(master_pwd_hash, plain_pwd)
            except OSError:
                raise DataAccessError()
        else:
            raise NoMasterPasswordError()

    def set_master_pwd(self, new_pwd: str):
        try:
            with open(self.master_pwd_file, 'w') as f:
                f.write(PasswordHasher().hash(new_pwd))
        except OSError:
            raise DataAccessError()
