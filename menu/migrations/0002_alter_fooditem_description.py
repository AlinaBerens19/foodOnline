# Generated by Django 4.1.4 on 2023-01-12 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fooditem',
            name='description',
            field=models.TextField(blank=True, max_length=250, unique=True),
        ),
    ]
