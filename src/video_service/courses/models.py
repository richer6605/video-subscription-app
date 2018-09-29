from django.db import models

from django.urls import reverse
from memberships.models import Membership

# Create your models here.
class Course(models.Model):
    slug = models.SlugField()
    title = models.CharField(max_length=120)
    description = models.TextField()
    allowed_memberships = models.ManyToManyField(Membership)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('courses:detail', kwargs={'slug': self.slug})

class Lesson(models.Model):
    slug = models.SlugField()
    title = models.CharField(max_length=120)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    position = models.IntegerField()
    ## This is used in the tutorial instead
    # video_url = models.CharField(max_length=200)
    video_url = models.URLField(max_length=200)
    thumbnail = models.ImageField()

    def __str__(self):
        return self.title