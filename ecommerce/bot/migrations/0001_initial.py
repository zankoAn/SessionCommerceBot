# Generated by Django 5.0.6 on 2024-07-03 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BotUpdateStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_update', models.BooleanField(default=False, verbose_name='update status')),
                ('update_msg', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(default='')),
                ('current_step', models.CharField(default='home', max_length=80, verbose_name='current step')),
                ('key', models.CharField(blank=True, max_length=200, null=True, verbose_name='base keyboard')),
                ('keys', models.TextField(blank=True, null=True, verbose_name='all other keys')),
                ('keys_per_row', models.PositiveIntegerField(blank=True, default=2, null=True, verbose_name='keys per row')),
                ('is_inline_keyboard', models.BooleanField(default=False, verbose_name='Is inline keyboard?')),
            ],
        ),
    ]
