# Написана руками: переименование вместе со сменой названия поля Django принимает за удаление
# колонки и новую колонку — коды из писем пропали бы. Здесь колонки переименовываются, данные на месте

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_usersession'),
    ]

    operations = [
        migrations.RenameField(
            model_name='customuser',
            old_name='activation_code',
            new_name='confirmation_code',
        ),
        migrations.RenameField(
            model_name='customuser',
            old_name='activation_code_attempts',
            new_name='confirmation_code_attempts',
        ),
        migrations.RenameField(
            model_name='customuser',
            old_name='activation_code_created_at',
            new_name='confirmation_code_created_at',
        ),
        migrations.AlterField(
            model_name='customuser',
            name='confirmation_code',
            field=models.CharField(blank=True, max_length=6, null=True, verbose_name='Код подтверждения'),
        ),
    ]
