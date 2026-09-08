# ¿Por qué imap_unordered puede ser más rápido que imap en la práctica?

imap está obligado a entregarte los resultados respetando rigurosamente el orden del iterable original. 
Si la tarea con el índice 0 se retrasa (por ejemplo, le toca un time.sleep alto), imap congelará el stream y no te entregará el resultado de la tarea 1, 
aunque esta última ya haya terminado hace tiempo. En cambio, imap_unordered prescinde de este bloqueo: worker que termina, 
resultado que se escupe inmediatamente al iterador. Esto evita que los workers rápidos se queden esperando pasivamente 
a los lentos solo por mantener un orden arbitrario.

# ¿Cuándo conviene usar apply_async en lugar de map?

map es ideal cuando tenés una colección homogénea de datos y querés aplicarles la misma función a todos. 
apply_async te conviene cuando tenés pocas tareas pero de naturaleza heterogénea (funciones totalmente distintas), 
o cuando querés un control fino sobre una tarea individual (por ejemplo, asignarle un timeout específico o verificar 
si ya terminó con .ready() ientras el proceso padre continúa haciendo otra cosa).

# ¿Qué pasaría si la duración de las tareas fuera constante?

Si todas las tareas duraran exactamente lo mismo, la diferencia de rendimiento entre imap e imap_unordered se reduciría al mínimo, 
ya que los elementos terminarían naturalmente en el mismo orden en que fueron despachados. De todas formas, imap_unordered 
seguiría teniendo una ventaja milimétrica al no requerir la lógica interna de ordenamiento que gestiona imap.