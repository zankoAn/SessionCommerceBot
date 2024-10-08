# Generated by Django 5.0.6 on 2024-07-15 16:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='status',
            field=models.CharField(choices=[('Success Transaction ✅', 'Paid'), ('Success Transaction And Pay more ✅', 'Paid Over'), ('Failed Transaction ❌', 'Fail'), ('⏳ In Progress', 'In Progress'), ('Wrong Amount Waiting ❌', 'Wrong Amount'), ('Already Paid ❌', 'Prepaid')], default='⏳ In Progress', max_length=50, verbose_name='session status'),
        ),
    ]
