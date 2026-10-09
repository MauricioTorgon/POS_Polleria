import os
import webbrowser
from threading import Timer
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from sqlalchemy import func

from models import db, Producto, Venta, VentaDetalle, Caja, Cliente, CuentaCobrar, Abono, Devolucion, MovimientoCaja, EntradaInventario
from seed import seed_products

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_products(db, Producto)


def get_open_caja():
    """Retorna la caja abierta actual o None."""
    return Caja.query.filter_by(estado='abierta').order_by(Caja.id.desc()).first()


# ──────────────────────────────────────────────
# Ruta principal
# ──────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


# ──────────────────────────────────────────────
# PRODUCTOS
# ──────────────────────────────────────────────
@app.route('/api/productos', methods=['GET'])
def list_productos():
    q = request.args.get('q', '')
    query = Producto.query.filter_by(activo=True)
    if q:
        query = query.filter(Producto.nombre.ilike(f'%{q}%'))
    productos = query.all()
    return jsonify({
        "ok": True,
        "data": [{"id": p.id, "codigo_barras": p.codigo_barras, "nombre": p.nombre, "precio": p.precio, "unidad_medida": p.unidad_medida, "stock": p.stock} for p in productos]
    })


@app.route('/api/productos', methods=['POST'])
def create_producto():
    data = request.json
    if not data or not all(k in data for k in ("codigo_barras", "nombre", "precio")):
        return jsonify({"ok": False, "error": "Datos incompletos"}), 400
    if Producto.query.filter_by(codigo_barras=data['codigo_barras']).first():
        return jsonify({"ok": False, "error": "Código de barras ya existe"}), 400

    producto = Producto(
        codigo_barras=data['codigo_barras'],
        nombre=data['nombre'],
        precio=float(data['precio']),
        unidad_medida=data.get('unidad_medida', 'Kg')
    )
    db.session.add(producto)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": producto.id, "codigo_barras": producto.codigo_barras, "nombre": producto.nombre, "precio": producto.precio, "unidad_medida": producto.unidad_medida, "stock": producto.stock}})


@app.route('/api/productos/codigo/<codigo>', methods=['GET'])
def get_producto_by_codigo(codigo):
    p = Producto.query.filter_by(codigo_barras=codigo, activo=True).first()
    if p:
        return jsonify({"ok": True, "data": {"id": p.id, "codigo_barras": p.codigo_barras, "nombre": p.nombre, "precio": p.precio, "unidad_medida": p.unidad_medida, "stock": p.stock}})
    return jsonify({"ok": False, "error": "Producto no encontrado"}), 404


@app.route('/api/productos/<int:id>', methods=['PUT'])
def update_producto(id):
    p = Producto.query.get(id)
    if not p:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    data = request.json
    if 'codigo_barras' in data:
        existing = Producto.query.filter(Producto.codigo_barras == data['codigo_barras'], Producto.id != id).first()
        if existing:
            return jsonify({"ok": False, "error": "El código de barras ya está en uso por otro producto"}), 400
        p.codigo_barras = data['codigo_barras']
    if 'nombre' in data:
        p.nombre = data['nombre']
    if 'precio' in data:
        p.precio = float(data['precio'])
    if 'unidad_medida' in data:
        p.unidad_medida = data['unidad_medida']
    if 'activo' in data:
        p.activo = bool(data['activo'])
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": p.id, "codigo_barras": p.codigo_barras, "nombre": p.nombre, "precio": p.precio, "unidad_medida": p.unidad_medida, "stock": p.stock, "activo": p.activo}})


# ──────────────────────────────────────────────
# VENTAS
# ──────────────────────────────────────────────
@app.route('/api/ventas', methods=['POST'])
def create_venta():
    caja = get_open_caja()
    if not caja:
        return jsonify({"ok": False, "error": "No hay caja abierta"}), 400

    data = request.json
    items = data.get('items', [])
    if not items:
        return jsonify({"ok": False, "error": "Venta sin artículos"}), 400

    cliente_id = data.get('cliente_id')
    es_credito = bool(cliente_id)
    total = sum(float(item['subtotal']) for item in items)
    pago = float(data.get('pago', 0.0))
    cambio = float(data.get('cambio', 0.0))
    estado_venta = 'credito' if es_credito else 'completada'

    venta = Venta(total=total, pago=pago, cambio=cambio, cliente_id=cliente_id, estado=estado_venta, caja_id=caja.id)
    db.session.add(venta)
    db.session.flush()

    for item in items:
        producto = Producto.query.get(item['producto_id'])
        if producto:
            producto.stock -= float(item['cantidad'])
            
        detalle = VentaDetalle(
            venta_id=venta.id,
            producto_id=item['producto_id'],
            cantidad=float(item['cantidad']),
            precio_unitario=float(item['precio_unitario']),
            descuento=float(item.get('descuento', 0.0)),
            subtotal=float(item['subtotal'])
        )
        db.session.add(detalle)

    if es_credito:
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            db.session.rollback()
            return jsonify({"ok": False, "error": "Cliente no encontrado"}), 404
        cuenta = CuentaCobrar(
            cliente_id=cliente.id,
            venta_id=venta.id,
            monto_original=total,
            monto_pendiente=total
        )
        cliente.saldo_pendiente += total
        db.session.add(cuenta)
    else:
        caja.ventas_total += total

    try:
        db.session.commit()
        return jsonify({"ok": True, "data": {"id": venta.id, "total": venta.total, "pago": venta.pago, "cambio": venta.cambio}})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/ventas', methods=['GET'])
def list_ventas():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    query = Venta.query
    if desde:
        try:
            query = query.filter(Venta.fecha >= datetime.strptime(desde, '%Y-%m-%d'))
        except ValueError:
            pass
    if hasta:
        try:
            h = datetime.strptime(hasta, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Venta.fecha <= h)
        except ValueError:
            pass

    ventas = query.order_by(Venta.fecha.desc()).all()
    data = []
    for v in ventas:
        data.append({
            "id": v.id,
            "fecha": v.fecha.isoformat(),
            "total": v.total,
            "cliente_id": v.cliente_id,
            "estado": v.estado,
            "caja_id": v.caja_id,
            "detalles": [{
                "producto_id": d.producto_id,
                "nombre": Producto.query.get(d.producto_id).nombre if Producto.query.get(d.producto_id) else "Desconocido",
                "cantidad": d.cantidad,
                "precio_unitario": d.precio_unitario,
                "descuento": d.descuento,
                "subtotal": d.subtotal
            } for d in v.detalles]
        })
    return jsonify({"ok": True, "data": data})


@app.route('/api/ventas/<int:id>', methods=['GET'])
def get_venta(id):
    v = Venta.query.get(id)
    if not v:
        return jsonify({"ok": False, "error": "Venta no encontrada"}), 404
    detalles = []
    for d in v.detalles:
        p = Producto.query.get(d.producto_id)
        detalles.append({
            "producto_id": d.producto_id,
            "nombre": p.nombre if p else "Desconocido",
            "cantidad": d.cantidad,
            "precio_unitario": d.precio_unitario,
            "descuento": d.descuento,
            "subtotal": d.subtotal,
            "unidad_medida": p.unidad_medida if p else 'Kg'
        })
    return jsonify({"ok": True, "data": {
        "id": v.id,
        "fecha": v.fecha.isoformat(),
        "total": v.total,
        "pago": v.pago,
        "cambio": v.cambio,
        "cliente_id": v.cliente_id,
        "estado": v.estado,
        "caja_id": v.caja_id,
        "detalles": detalles
    }})


# ──────────────────────────────────────────────
# CAJA Y MOVIMIENTOS
# ──────────────────────────────────────────────
@app.route('/api/caja/estado', methods=['GET'])
def get_caja_estado():
    caja = Caja.query.order_by(Caja.id.desc()).first()
    if not caja:
        return jsonify({"ok": True, "data": None})
    return jsonify({"ok": True, "data": {
        "id": caja.id,
        "fecha_apertura": caja.fecha_apertura.isoformat() if caja.fecha_apertura else None,
        "fecha_cierre": caja.fecha_cierre.isoformat() if caja.fecha_cierre else None,
        "fondo_inicial": caja.fondo_inicial,
        "ventas_total": caja.ventas_total,
        "devoluciones_total": caja.devoluciones_total,
        "cobros_deudas": caja.cobros_deudas,
        "ingresos_total": caja.ingresos_total,
        "egresos_total": caja.egresos_total,
        "fondo_final": caja.fondo_final,
        "estado": caja.estado
    }})


@app.route('/api/caja/abrir', methods=['POST'])
def abrir_caja():
    if get_open_caja():
        return jsonify({"ok": False, "error": "Ya hay una caja abierta"}), 400
    fondo = float(request.json.get('fondo_inicial', 0.0))
    caja = Caja(fondo_inicial=fondo)
    db.session.add(caja)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": caja.id, "fondo_inicial": caja.fondo_inicial}})


@app.route('/api/caja/cerrar', methods=['POST'])
def cerrar_caja():
    caja = get_open_caja()
    if not caja:
        return jsonify({"ok": False, "error": "No hay caja abierta"}), 400
    caja.fecha_cierre = datetime.now()
    caja.estado = 'cerrada'
    caja.fondo_final = caja.fondo_inicial + caja.ventas_total - caja.devoluciones_total + caja.cobros_deudas + caja.ingresos_total - caja.egresos_total
    db.session.commit()
    return jsonify({"ok": True, "data": {
        "id": caja.id,
        "fondo_inicial": caja.fondo_inicial,
        "ventas_total": caja.ventas_total,
        "devoluciones_total": caja.devoluciones_total,
        "cobros_deudas": caja.cobros_deudas,
        "ingresos_total": caja.ingresos_total,
        "egresos_total": caja.egresos_total,
        "fondo_final": caja.fondo_final
    }})


@app.route('/api/caja/fondo', methods=['PUT'])
def actualizar_fondo_caja():
    caja = get_open_caja()
    if not caja:
        return jsonify({"ok": False, "error": "No hay caja abierta"}), 400
    if 'fondo_inicial' not in request.json:
        return jsonify({"ok": False, "error": "Falta fondo_inicial"}), 400
    caja.fondo_inicial = float(request.json['fondo_inicial'])
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": caja.id, "fondo_inicial": caja.fondo_inicial}})


@app.route('/api/caja/movimientos', methods=['POST'])
def registrar_movimiento():
    caja = get_open_caja()
    if not caja:
        return jsonify({"ok": False, "error": "No hay caja abierta"}), 400
    data = request.json
    tipo = data.get('tipo')
    monto = float(data.get('monto', 0))
    if tipo not in ['ingreso', 'egreso'] or monto <= 0:
        return jsonify({"ok": False, "error": "Tipo o monto inválido"}), 400
    
    mov = MovimientoCaja(
        caja_id=caja.id,
        tipo=tipo,
        monto=monto,
        concepto=data.get('concepto', '')
    )
    db.session.add(mov)
    
    if tipo == 'ingreso':
        caja.ingresos_total += monto
    else:
        caja.egresos_total += monto
        
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": mov.id, "tipo": mov.tipo, "monto": mov.monto}})


# ──────────────────────────────────────────────
# CLIENTES Y ABONOS
# ──────────────────────────────────────────────
@app.route('/api/clientes', methods=['GET'])
def list_clientes():
    q = request.args.get('q', '')
    query = Cliente.query
    if q:
        query = query.filter(Cliente.nombre.ilike(f'%{q}%'))
    return jsonify({"ok": True, "data": [{
        "id": c.id,
        "nombre": c.nombre,
        "telefono": c.telefono,
        "saldo_pendiente": c.saldo_pendiente
    } for c in query.all()]})


@app.route('/api/clientes', methods=['POST'])
def create_cliente():
    if not request.json or 'nombre' not in request.json:
        return jsonify({"ok": False, "error": "Falta el nombre"}), 400
    cliente = Cliente(nombre=request.json['nombre'], telefono=request.json.get('telefono', ''))
    db.session.add(cliente)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": cliente.id, "nombre": cliente.nombre}})


@app.route('/api/clientes/<int:id>', methods=['GET'])
def get_cliente(id):
    c = Cliente.query.get(id)
    if not c:
        return jsonify({"ok": False, "error": "Cliente no encontrado"}), 404
    cuentas = [{
        "id": cu.id,
        "venta_id": cu.venta_id,
        "monto_original": cu.monto_original,
        "monto_pendiente": cu.monto_pendiente,
        "fecha": cu.fecha.isoformat(),
        "estado": cu.estado
    } for cu in c.cuentas]
    return jsonify({"ok": True, "data": {
        "id": c.id,
        "nombre": c.nombre,
        "telefono": c.telefono,
        "saldo_pendiente": c.saldo_pendiente,
        "cuentas": cuentas
    }})


@app.route('/api/abonos', methods=['POST'])
def crear_abono():
    data = request.json
    monto = float(data.get('monto', 0))
    if monto <= 0:
        return jsonify({"ok": False, "error": "Monto inválido"}), 400

    cuenta = CuentaCobrar.query.get(data.get('cuenta_id'))
    if not cuenta:
        return jsonify({"ok": False, "error": "Cuenta no encontrada"}), 404

    cliente = Cliente.query.get(cuenta.cliente_id)
    if monto > cuenta.monto_pendiente:
        return jsonify({"ok": False, "error": "El abono supera el monto pendiente"}), 400

    cuenta.monto_pendiente -= monto
    if cuenta.monto_pendiente <= 0.001:
        cuenta.estado = 'pagada'
    cliente.saldo_pendiente -= monto

    abono = Abono(cuenta_id=cuenta.id, cliente_id=cliente.id, monto=monto, nota=data.get('nota', ''))
    db.session.add(abono)

    caja = get_open_caja()
    if caja:
        caja.cobros_deudas += monto

    db.session.commit()
    return jsonify({"ok": True, "data": {"id": abono.id, "monto_pendiente": cuenta.monto_pendiente}})


# ──────────────────────────────────────────────
# DEVOLUCIONES
# ──────────────────────────────────────────────
@app.route('/api/devoluciones', methods=['POST'])
def registrar_devolucion():
    caja = get_open_caja()
    if not caja:
        return jsonify({"ok": False, "error": "No hay caja abierta"}), 400

    data = request.json
    venta = Venta.query.get(data.get('venta_id'))
    if not venta:
        return jsonify({"ok": False, "error": "Venta no encontrada"}), 404
    if venta.estado == 'devuelta':
        return jsonify({"ok": False, "error": "Venta ya devuelta"}), 400

    monto_devuelto = float(data.get('monto_devuelto', 0))
    venta.estado = 'devuelta'

    devolucion = Devolucion(
        venta_id=venta.id,
        monto_devuelto=monto_devuelto,
        motivo=data.get('motivo', ''),
        caja_id=caja.id
    )
    db.session.add(devolucion)
    caja.devoluciones_total += monto_devuelto
    
    # Retornar stock
    for detalle in venta.detalles:
        producto = Producto.query.get(detalle.producto_id)
        if producto:
            producto.stock += detalle.cantidad
            
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": devolucion.id}})


# ──────────────────────────────────────────────
# INVENTARIO
# ──────────────────────────────────────────────
@app.route('/api/inventario/entradas', methods=['POST'])
def registrar_entrada():
    data = request.json
    producto_id = data.get('producto_id')
    cantidad = float(data.get('cantidad', 0))
    if not producto_id or cantidad <= 0:
        return jsonify({"ok": False, "error": "Datos inválidos"}), 400
        
    producto = Producto.query.get(producto_id)
    if not producto:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
        
    entrada = EntradaInventario(
        producto_id=producto.id,
        cantidad=cantidad,
        nota=data.get('nota', '')
    )
    producto.stock += cantidad
    db.session.add(entrada)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": entrada.id, "nuevo_stock": producto.stock}})


@app.route('/api/inventario/entradas', methods=['GET'])
def get_entradas():
    entradas = EntradaInventario.query.order_by(EntradaInventario.fecha.desc()).all()
    data = []
    for e in entradas:
        data.append({
            "id": e.id,
            "producto": e.producto.nombre if e.producto else "Desconocido",
            "cantidad": e.cantidad,
            "unidad_medida": e.producto.unidad_medida if e.producto else "Kg",
            "nota": e.nota,
            "fecha": e.fecha.isoformat()
        })
    return jsonify({"ok": True, "data": data})


# ──────────────────────────────────────────────
# REPORTES E INVENTARIO
# ──────────────────────────────────────────────
@app.route('/api/reportes/inventario', methods=['GET'])
def get_reporte_inventario():
    productos = Producto.query.all()
    data = []
    for p in productos:
        data.append({
            "id": p.id,
            "codigo": p.codigo_barras,
            "articulo": p.nombre,
            "unidad_medida": p.unidad_medida,
            "existencia": p.stock,
            "precio": p.precio
        })
    return jsonify({"ok": True, "data": data})

@app.route('/api/reportes/ventas', methods=['GET'])
def get_reporte():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    query = db.session.query(
        Producto.nombre.label('articulo'),
        Producto.unidad_medida.label('unidad_medida'),
        func.sum(VentaDetalle.cantidad).label('cantidad'),
        func.sum(VentaDetalle.subtotal).label('total')
    ).join(
        VentaDetalle, Producto.id == VentaDetalle.producto_id
    ).join(
        Venta, Venta.id == VentaDetalle.venta_id
    ).filter(
        Venta.estado != 'devuelta'
    )

    if desde:
        try:
            query = query.filter(Venta.fecha >= datetime.strptime(desde, '%Y-%m-%d'))
        except ValueError:
            pass
    if hasta:
        try:
            query = query.filter(Venta.fecha <= datetime.strptime(hasta, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError:
            pass

    resultados = query.group_by(Producto.id).all()
    data = [{"articulo": r.articulo, "unidad_medida": r.unidad_medida, "cantidad": round(r.cantidad, 3), "total": round(r.total, 2)} for r in resultados]
    grand_total = round(sum(r.total for r in resultados), 2)
    return jsonify({"ok": True, "data": data, "grand_total": grand_total})


# ──────────────────────────────────────────────
# TICKET
# ──────────────────────────────────────────────
@app.route('/api/ticket/<int:venta_id>', methods=['GET'])
def get_ticket(venta_id):
    v = Venta.query.get(venta_id)
    if not v:
        return jsonify({"ok": False, "error": "Venta no encontrada"}), 404
    detalles = []
    for d in v.detalles:
        p = Producto.query.get(d.producto_id)
        detalles.append({
            "descripcion": p.nombre if p else "Desconocido",
            "cantidad": d.cantidad,
            "precio": d.precio_unitario,
            "descuento": d.descuento,
            "importe": d.subtotal,
            "unidad_medida": p.unidad_medida if p else 'Kg'
        })
    return jsonify({"ok": True, "data": {
        "negocio": "POLLOS ANDY",
        "fecha": v.fecha.strftime('%d/%m/%Y'),
        "hora": v.fecha.strftime('%H:%M'),
        "ticket_id": v.id,
        "caja_id": v.caja_id,
        "estado": v.estado,
        "detalles": detalles,
        "total": v.total,
        "pago": v.pago,
        "cambio": v.cambio
    }})


# ──────────────────────────────────────────────
# AUTO-ABRIR NAVEGADOR E INICIAR SERVIDOR
# ──────────────────────────────────────────────
def open_browser():
    webbrowser.open('http://127.0.0.1:5000/')


if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_RELOADER') != 'true':
        Timer(1.5, open_browser).start()
    app.run(debug=True, port=5000)
