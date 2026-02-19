from django.db import models

class Movie(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)
    genre = models.CharField(max_length=50)
    language = models.CharField(max_length=50)
    trailer_url = models.URLField(blank=True, null=True, help_text="YouTube trailer URL (e.g., https://www.youtube.com/watch?v=xxxxx)")

    def __str__(self):
        return self.name
    
    @property
    def trailer_embed_url(self):
        if self.trailer_url:
            video_id = None
            if 'youtube.com/watch?v=' in self.trailer_url:
                video_id = self.trailer_url.split('watch?v=')[-1].split('&')[0].split('?')[0]
            elif 'youtu.be/' in self.trailer_url:
                video_id = self.trailer_url.split('youtu.be/')[-1].split('?')[0].split('&')[0]
            elif 'youtube.com/embed/' in self.trailer_url:
                video_id = self.trailer_url.split('embed/')[-1].split('?')[0].split('&')[0]
            
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"
        return None
