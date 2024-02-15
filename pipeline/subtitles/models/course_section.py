from django.db import models


class CourseSection(models.Model):
    """A course section is on openHPI and openSAP a course week.
    On openWHO it is a module."""

    title = models.CharField(max_length=200)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    ext_id = models.CharField(max_length=200, unique=False)
    index = models.IntegerField(null=True, blank=True, db_index=True)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)

    class Meta:
        ordering = ['index']
        unique_together = ['tenant_id', 'ext_id']

    def __str__(self):
        return self.title