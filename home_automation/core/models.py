from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class User(AbstractUser):
    # Used to link family users to the homeowner who created them
    homeowner = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='family_members'
    )
    
    def is_admin(self):
        return self.groups.filter(name='admin').exists()
    
    def is_homeowner(self):
        return self.groups.filter(name='homeowner').exists()
    
    def is_family(self):
        return self.groups.filter(name='family').exists()
    
    def is_technician(self):
        return self.groups.filter(name='technician').exists()
    
    def __str__(self):
        return self.username

class Controller(models.Model):
    type = models.CharField(max_length=255, default="Raspberry Pi 3")
    mac_address = models.CharField(max_length=255, unique=True)
    homeowner = models.OneToOneField(User, on_delete=models.CASCADE)
    max_slaves = models.PositiveIntegerField(default=10)
    
    def __str__(self):
        return f"Controller {self.type} → {self.mac_address} → {self.homeowner.username}"

class Room(models.Model):
    name = models.CharField(max_length=100)
    homeowner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rooms',
        limit_choices_to={'groups__name': 'homeowner'}
    )
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, related_name='rooms')
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'homeowner'],
                name='unique_room_name_per_homeowner'
            )
        ]
    
    def __str__(self):
        return self.name

class SlaveDevice(models.Model):
    controller = models.ForeignKey(Controller, on_delete=models.CASCADE, related_name='slaves')
    name = models.CharField(max_length=100)
    mac_address = models.CharField(max_length=255, unique=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'controller'],
                name='unique_slave_name_per_controller'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.mac_address})"

class Appliance(models.Model):
    name = models.CharField(max_length=100)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    wattage = models.IntegerField(null=False, help_text="Power rating in watts (W)")
    slave = models.ForeignKey(SlaveDevice, null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.IntegerField(
        help_text="Relay channel (0-7)", 
        validators=[MinValueValidator(0), MaxValueValidator(7)], 
        default=1
    )
    
    class Meta:
        constraints = [
            # Ensure no two appliances use the same channel on the same slave device
            models.UniqueConstraint(
                fields=['slave', 'channel'],
                name='unique_slave_channel',
                condition=models.Q(slave__isnull=False)  # Only apply when slave is not null
            ),
            # Ensure appliance names are unique within each room
            models.UniqueConstraint(
                fields=['name', 'room'],
                name='unique_appliance_name_per_room'
            )
        ]
    
    def __str__(self):
        return f"{self.name} in {self.room.name} of {self.room.controller.homeowner.username}"

class ApplianceUsageLog(models.Model):
    appliance = models.ForeignKey(Appliance, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    stop_time = models.DateTimeField(null=True, blank=True)
    energy_consumed = models.FloatField(null=True, blank=True)
    
    class Meta:
        constraints = [
            # Ensure stop_time is after start_time
            models.CheckConstraint(
                check=models.Q(stop_time__isnull=True) | models.Q(stop_time__gt=models.F('start_time')),
                name='valid_time_range'
            )
        ]
        indexes = [
            models.Index(fields=['appliance', 'start_time']),
            models.Index(fields=['start_time', 'stop_time']),
        ]
    
    def __str__(self):
        return f"{self.appliance.name} | {self.start_time} - {self.stop_time or 'running...'}"