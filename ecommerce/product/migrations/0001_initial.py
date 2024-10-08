# Generated by Django 5.0.6 on 2024-07-03 14:45

import django.db.models.deletion
import ecommerce.product.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proxy', models.CharField(blank=True, max_length=50, verbose_name='proxy(ip:port)')),
                ('api_id', models.CharField(blank=True, max_length=20, verbose_name='api id')),
                ('api_hash', models.CharField(blank=True, max_length=50, verbose_name='api hash')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='phone number')),
                ('app_version', models.CharField(blank=True, max_length=30, null=True, verbose_name='App Version')),
                ('device_model', models.CharField(blank=True, max_length=30, null=True, verbose_name='Device Model')),
                ('system_version', models.CharField(blank=True, max_length=30, null=True, verbose_name='System Version')),
                ('password', models.CharField(blank=True, default='', max_length=64, verbose_name='account password')),
                ('status', models.CharField(choices=[('فعال ✅', 'Active'), ('غیر فعال ❌', 'Disable'), ('محدود ⚠️', 'Limit'), ('فروخته شد 💸', 'Purchased'), ('در انتظار ⏳', 'Wait'), ('نامشخص 🔘', 'Unknown')], default='نامشخص 🔘', max_length=50, verbose_name='session status')),
                ('session_string', models.CharField(max_length=400, verbose_name='session string')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='created time')),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='product name')),
                ('country_code', models.CharField(default='', help_text='us, ir, uk and etc..', max_length=50, verbose_name='country code')),
                ('phone_code', models.CharField(default='', help_text='+98, +1, +964, +234 and etc..', max_length=50, verbose_name='phone code')),
                ('price', models.PositiveIntegerField(default=0, verbose_name='product price')),
                ('is_active', models.BooleanField(default=True, verbose_name='is active product?')),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('login_code', models.CharField(blank=True, max_length=20, null=True, verbose_name='login code')),
                ('price', models.IntegerField(default=0, verbose_name='price')),
                ('track_id', models.CharField(default=ecommerce.product.models.generate_short_uuid, max_length=80, verbose_name='tracking id')),
                ('status', models.CharField(choices=[('انجام شد ✅', 'Down'), ('رد شد ❌', 'Reject'), ('در صف ', 'Waiting')], default='در صف ', max_length=30)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='created time')),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='session', to='product.accountsession')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='accountsession',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accounts', to='product.product'),
        ),
    ]
