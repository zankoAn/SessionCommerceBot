# Generated by Django 5.0.6 on 2024-07-03 14:45

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('Success Transaction ✅', 'Paid'), ('Success Transaction And Pay more ✅', 'Paid Over'), ('Failed Transaction ❌', 'Fail'), ('⏳ In Progress', 'In Progress'), ('Wrong Amount Waiting ❌', 'Wrong Amount')], default='⏳ In Progress', max_length=50, verbose_name='session status')),
                ('payment_method', models.CharField(choices=[('ZarinPal', 'Zarinpal'), ('PerfectMoney', 'Perfect Money'), ('Cryptocurrency', 'Crypto')], default='ZarinPal', max_length=50, verbose_name='payment method')),
                ('amount_rial', models.IntegerField(blank=True, null=True, verbose_name='amount rial')),
                ('amount_usd', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='amount dollar')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='creation time')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='update time')),
                ('payer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PerfectMoneyPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evoucher', models.CharField(blank=True, max_length=10, null=True, verbose_name='E-voucher')),
                ('activation_code', models.CharField(blank=True, max_length=16, null=True, verbose_name='activation code')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfectmoney', to='payment.transaction', verbose_name='related transaction')),
            ],
        ),
        migrations.CreateModel(
            name='CryptoPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_addres', models.CharField(blank=True, max_length=255, null=True, verbose_name='payer wallet address')),
                ('order_id', models.CharField(blank=True, max_length=50, null=True, unique=True, verbose_name='order id')),
                ('tx_hash', models.CharField(blank=True, max_length=255, null=True, verbose_name='transaction hash')),
                ('network', models.CharField(blank=True, max_length=20, null=True, verbose_name='blockchain network')),
                ('currency', models.CharField(blank=True, max_length=20, null=True, verbose_name='invoice currency')),
                ('payer_currency', models.CharField(blank=True, max_length=20, null=True, verbose_name='actuall paid currency')),
                ('payment_amount_coin', models.DecimalField(blank=True, decimal_places=5, max_digits=10, null=True, verbose_name='actual pay amount crypto')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='crypto', to='payment.transaction', verbose_name='related transaction')),
            ],
        ),
        migrations.CreateModel(
            name='ZarinPalPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('authority', models.CharField(blank=True, max_length=70, null=True, unique=True, verbose_name='authority id')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='zarinpal', to='payment.transaction', verbose_name='related transaction')),
            ],
        ),
    ]
