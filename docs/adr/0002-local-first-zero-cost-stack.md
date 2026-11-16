# ADR 0002: Stack local-first y de coste cero

## Estado
Aceptado

## Contexto
Buscamos reproducibilidad total, privacidad absoluta (sin que ningún dato de negocio salga de la máquina local) y coste cero en APIs durante el desarrollo, las pruebas y la evaluación en CI.

## Decisión
- **Inferencia LLM:** Servidor local Ollama configurado mediante variables de entorno (`OLLAMA_MODEL`, por defecto `qwen2.5-coder:7b`). La lógica del grafo utiliza salidas estructuradas (Pydantic) para poder intercambiar y comparar modelos sin modificar el código.
- **Base de datos:** PostgreSQL ejecutándose en Docker Desktop, poblado de forma determinista con una semilla fija para que los tests de integración y las evaluaciones puedan verificar cifras exactas.
- **Estrategia de pruebas:** Los tests unitarios simulan el LLM para ejecutarse de forma rápida y determinista; los tests de integración se ejecutan contra el contenedor PostgreSQL real.

## Consecuencias
- **Positivas:** Cero costes recurrentes de API, pruebas de regresión deterministas y privacidad total de los datos.
- **Negativas:** Los modelos locales de ~7B parámetros tienen ventanas de contexto más pequeñas y menor capacidad de razonamiento en consultas complejas con múltiples `JOIN` que los modelos fronterizos en la nube, lo que hace imprescindible contar con una capa semántica dedicada (Hito 4) y un bucle de autocorrección (Hito 3).