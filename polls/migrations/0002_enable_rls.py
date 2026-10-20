"""Supabase: `public` şemasındaki tüm Django tablolarında Row Level Security'yi açar.

Supabase, `public` şemasını varsayılan olarak otomatik REST API (Data API) ile dışarı açar ve yeni
tablolara `anon` / `authenticated` rollerine erişim verir. Biz bu API'yi kullanmıyoruz; Data API
kapatılsa bile RLS ikinci bir güvenlik katmanı olarak açık kalır. Policy tanımlamadığımız için bu
rollere hiçbir satır görünmez. Django, tabloların sahibi olan rolle bağlandığı için etkilenmez.

Sadece PostgreSQL'de çalışır; yerelde SQLite'ta hiçbir şey yapmaz.
NOT: Bu migration yalnızca çalıştığı andaki tabloları kapsar. İleride yeni tablo ekleyen her
migration'dan sonra aynı işlem tekrarlanmalı (bkz. DEPLOY.md, "Yeni tablo eklenince").
"""

from django.db import migrations


def _set_rls(schema_editor, enable):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    action = "ENABLE" if enable else "DISABLE"
    with connection.cursor() as cursor:
        for table in connection.introspection.table_names(cursor):
            cursor.execute(f"ALTER TABLE {connection.ops.quote_name(table)} {action} ROW LEVEL SECURITY")


def enable_rls(apps, schema_editor):
    _set_rls(schema_editor, enable=True)


def disable_rls(apps, schema_editor):
    _set_rls(schema_editor, enable=False)


class Migration(migrations.Migration):
    dependencies = [
        ("polls", "0001_initial"),
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
