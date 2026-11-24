import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuramos el cliente para apuntar a los servidores de Groq
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Usamos un modelo gratuito y muy rápido de Groq (Llama 3)
MODELO = "openai/gpt-oss-120b"
MAX_VUELTAS = 6


# 0. BASE (tu código)

inventario = [
    {"producto": "Camisa",   "precio": 45000,  "stock": 20},
    {"producto": "Gorra",    "precio": 30000,  "stock": 5},
    {"producto": "Pantalón", "precio": 89000,  "stock": 12},
    {"producto": "Medias",   "precio": 8000,   "stock": 40},
    {"producto": "Zapatos",  "precio": 150000, "stock": 3},
]

with open("inventario.json", "w", encoding="utf-8") as f:
    json.dump(inventario, f, indent=4, ensure_ascii=False)

with open("inventario.json", "r", encoding="utf-8") as f:
    datos = json.load(f)

datos.append({"producto": "Bufanda", "precio": 25000, "stock": 15})

with open("inventario.json", "w", encoding="utf-8") as f:
    json.dump(datos, f, indent=4, ensure_ascii=False)

stock_bajo = [producto for producto in datos if producto["stock"] < 10]
print("Productos con stock menor a 10:")
for item in stock_bajo:
    print(item)


class CarritoCompras:
    def __init__(self):
        self.productos = []
    def agregar_producto(self, producto, precio, stock):
        self.productos.append({"producto": producto, "precio": precio, "stock": stock})
    def guardar(self, archivo):
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(self.productos, f, indent=4, ensure_ascii=False)
    def cargar(self, archivo):
        with open(archivo, "r", encoding="utf-8") as f:
            self.productos = json.load(f)
    def mostrar(self):
        for p in self.productos:
            print(f"- {p['producto']} | Precio: ${p['precio']} | Stock: {p['stock']}")


carrito1 = CarritoCompras()
carrito1.agregar_producto("Camisa", 45000, 2)
carrito1.agregar_producto("Gorra", 30000, 1)
carrito1.guardar("carrito.json")

carrito2 = CarritoCompras()
carrito2.cargar("carrito.json")
carrito2.mostrar()


# 2. FUNCIONES DE LA TIENDA (herramientas reales)

ENVIOS = {"Cali": 10000, "Popayán": 12000, "Bogotá": 15000}
ENVIO_DEFAULT = 20000

def _buscar_producto(nombre):
    for p in datos:
        if p["producto"].lower() == nombre.lower().strip():
            return p
    return None

def consultar_producto(nombre):
    p = _buscar_producto(nombre)
    if p is None:
        raise KeyError(f"Producto '{nombre}' no existe en el inventario")
    return json.dumps(p, ensure_ascii=False)

def calcular_pedido(items, ciudad):
    if not isinstance(items, list) or not items:
        raise ValueError("items debe ser una lista no vacía")
    if not isinstance(ciudad, str) or not ciudad.strip():
        raise ValueError("La ciudad es obligatoria")

    subtotal = 0
    detalle = []
    for it in items:
        if not isinstance(it, dict):
            raise TypeError("Cada item debe ser un diccionario")
        nombre = it.get("producto")
        cantidad = it.get("cantidad")
        if nombre is None or cantidad is None:
            raise KeyError("Cada item requiere 'producto' y 'cantidad'")
        if not isinstance(cantidad, int):
            raise TypeError("La cantidad debe ser entera")
        if cantidad <= 0:
            raise ValueError(f"Cantidad inválida para {nombre}: {cantidad}")

        p = _buscar_producto(nombre)
        if p is None:
            raise KeyError(f"Producto '{nombre}' no existe")
        if cantidad > p["stock"]:
            raise ValueError(f"Stock insuficiente de {nombre}: pediste {cantidad}, hay {p['stock']}")

        linea = p["precio"] * cantidad
        subtotal += linea
        detalle.append({
            "producto": p["producto"], "cantidad": cantidad,
            "precio_unitario": p["precio"], "subtotal": linea,
        })

    envio = ENVIOS.get(ciudad.strip().title(), ENVIO_DEFAULT)
    total = subtotal + envio
    return json.dumps({
        "detalle": detalle, "subtotal": subtotal,
        "envio": envio, "total": total, "ciudad": ciudad,
    }, ensure_ascii=False)


# 1 y 2.1. Esquemas de herramientas (Formato OpenAI/Groq)

HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_producto",
            "description": "Consulta precio y stock de un producto del inventario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del producto"}
                },
                "required": ["nombre"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_pedido",
            "description": "Calcula subtotal, envío y total de un pedido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "producto": {"type": "string"},
                                "cantidad": {"type": "integer"},
                            },
                            "required": ["producto", "cantidad"],
                        },
                    },
                    "ciudad": {"type": "string"},
                },
                "required": ["items", "ciudad"],
            },
        }
    }
]

FUNCIONES = {
    "consultar_producto": consultar_producto,
    "calcular_pedido": calcular_pedido,
}


# 5.2. guardar_pedido + registrar_pedidos

ARCHIVO_PEDIDOS = "pedidos.json"

def _leer_pedidos():
    if not os.path.exists(ARCHIVO_PEDIDOS): return []
    with open(ARCHIVO_PEDIDOS, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []

def guardar_pedido(items, ciudad):
    resultado = json.loads(calcular_pedido(items, ciudad))
    print("\n--- Resumen del pedido ---")
    for d in resultado["detalle"]:
        print(f"  {d['cantidad']} x {d['producto']} = ${d['subtotal']}")
    print(f"  Subtotal: ${resultado['subtotal']}")
    print(f"  Envío ({resultado['ciudad']}): ${resultado['envio']}")
    print(f"  TOTAL: ${resultado['total']}")
    resp = input("¿Confirmas el pedido? (s/n): ").strip().lower()
    if resp != "s":
        return json.dumps({"guardado": False, "motivo": "cancelado por el usuario"})

    pedidos = _leer_pedidos()
    numero = len(pedidos) + 1
    pedido = {"numero": numero, **resultado}
    pedidos.append(pedido)
    with open(ARCHIVO_PEDIDOS, "w", encoding="utf-8") as f:
        json.dump(pedidos, f, indent=4, ensure_ascii=False)
    return json.dumps({"guardado": True, "numero": numero, "total": resultado["total"]})

def registrar_pedidos():
    if "guardar_pedido" not in FUNCIONES:
        HERRAMIENTAS.append({
            "type": "function",
            "function": {
                "name": "guardar_pedido",
                "description": "Guarda un pedido tras confirmación del usuario.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "producto": {"type": "string"},
                                    "cantidad": {"type": "integer"},
                                },
                                "required": ["producto", "cantidad"],
                            },
                        },
                        "ciudad": {"type": "string"},
                    },
                    "required": ["items", "ciudad"],
                },
            }
        })
        FUNCIONES["guardar_pedido"] = guardar_pedido


# 2.2. ejecutar_herramienta

def ejecutar_herramienta(nombre, args):
    try:
        if nombre not in FUNCIONES:
            raise KeyError(f"Herramienta '{nombre}' no existe")
        resultado = FUNCIONES[nombre](**args)
        return {"ok": True, "resultado": resultado}
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# 3.1. Ciclo del agente (Adaptado a OpenAI/Groq)

SISTEMA = (
    "Eres el asistente de una tienda. Reglas:\n"
    "- Usa 'consultar_producto' para precios y stock.\n"
    "- Usa 'calcular_pedido' para TODOS los totales.\n"
    "- Si falta la ciudad, pregúntala; no inventes datos.\n"
    "- Si el usuario pide guardar/confirmar, usa 'guardar_pedido'.\n"
    "- Responde en español, breve y claro."
)

def agente(pregunta, historial=None, verbose=False):
    if historial is None:
        historial = []
    
    mensajes = [{"role": "system", "content": SISTEMA}]
    mensajes.extend(historial)
    mensajes.append({"role": "user", "content": pregunta})

    for vuelta in range(1, MAX_VUELTAS + 1):
        try:
            resp = client.chat.completions.create(
                model=MODELO,
                messages=mensajes,
                tools=HERRAMIENTAS,
                tool_choice="auto",
                max_tokens=1024
            )
        except Exception as e:
            return f"[Error del modelo: {e}]"

        msg = resp.choices[0].message

        if verbose:
            print(f"\n[Vuelta {vuelta}] finish_reason={resp.choices[0].finish_reason}")

        if not msg.tool_calls:
            return msg.content or "(sin respuesta)"

        # Hay llamadas a herramientas
        mensajes.append(msg)
        
        for tool_call in msg.tool_calls:
            nombre = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            
            if verbose:
                print(f"  -> Tool: {nombre}  args={args}")
                
            salida = ejecutar_herramienta(nombre, args)
            contenido = salida["resultado"] if salida["ok"] else salida["error"]
            
            mensajes.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": nombre,
                "content": contenido
            })

    return "⚠️ Se alcanzó el máximo de vueltas sin respuesta final."


# 4.1. Chat de consola

def chat():
    historial = []
    print("Chat de tienda (escribe 'salir' para terminar)\n")
    while True:
        texto = input("Tú: ").strip()
        if not texto: continue
        if texto.lower() == "salir": break
        respuesta = agente(texto, historial)
        print(f"Agente: {respuesta}\n")
        historial.append({"role": "user", "content": texto})
        historial.append({"role": "assistant", "content": respuesta})
    return historial


# Reto integrador

ARCHIVO_CONV = "conversacion_tienda.json"

def chat_integrador():
    registrar_pedidos()
    historial = []
    print("\n=== Asistente de Tienda (reto integrador) ===\n")
    while True:
        try:
            texto = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto: continue
        if texto.lower() == "salir": break

        contexto = historial[-8:] if len(historial) >= 8 else historial
        try:
            respuesta = agente(texto, contexto)
        except Exception as e:
            print(f"Agente: [Error temporal] {e}\n")
            continue

        print(f"Agente: {respuesta}\n")
        historial.append({"role": "user", "content": texto})
        historial.append({"role": "assistant", "content": respuesta})

    with open(ARCHIVO_CONV, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
    print(f"\nConversación guardada en {ARCHIVO_CONV}")


# Pruebas

if __name__ == "__main__":
    print("\n--- 5.1 Pruebas de error ---")
    casos = [
        ("consultar_producto", {"nombre": "pijamas"}),
        ("calcular_pedido", {"items": [{"producto": "Camisa", "cantidad": 0}], "ciudad": "Cali"}),
        ("calcular_pedido", {"items": [{"producto": "Zapatos", "cantidad": 9}], "ciudad": "Cali"}),
        ("calcular_pedido", {"items": [{"producto": "Falda", "cantidad": 1}], "ciudad": "Cali"}),
        ("herramienta_inventada", {}),
    ]
    for nombre, args in casos:
        r = ejecutar_herramienta(nombre, args)
        print(f"  {nombre}: error={not r['ok']}  ->  {r.get('error', r.get('resultado'))}")

    print("\n--- 3.2 Agente en acción ---")
    print(agente("Quiero 2 pantalones y unos zapatos, envío a Cali.", verbose=True))

    print("\n--- 4.2 Casos límite ---")
    for q in [
        "¿Cuánto cuestan las medias?",
        "¿Venden pijamas?",
        "Quiero 2 pantalones y unos zapatos a Cali",
        "Quiero 2 camisas y 1 pantalón a Popayán",
        "Quiero 6 gorras a Bogotá",
        "¿Cuál es la capital de Francia?",
    ]:
        print(f"\n>> {q}")
        print(agente(q))

    # Descomenta la siguiente línea para probar el chat completo del reto integrador
    # chat_integrador()