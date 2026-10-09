from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    unidad_medida = db.Column(db.String(10), default='Kg')  # 'Kg' o 'Pza'
    stock = db.Column(db.Float, default=0.0)
    activo = db.Column(db.Boolean, default=True)

class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    total = db.Column(db.Float, nullable=False)
    pago = db.Column(db.Float, default=0.0)
    cambio = db.Column(db.Float, default=0.0)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    estado = db.Column(db.String(20), default='completada')
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    detalles = db.relationship('VentaDetalle', backref='venta', lazy=True)

class VentaDetalle(db.Model):
    __tablename__ = 'venta_detalle'
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    descuento = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, nullable=False)

class Caja(db.Model):
    __tablename__ = 'caja'
    id = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, default=datetime.now)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    fondo_inicial = db.Column(db.Float, nullable=False)
    ventas_total = db.Column(db.Float, default=0.0)
    devoluciones_total = db.Column(db.Float, default=0.0)
    cobros_deudas = db.Column(db.Float, default=0.0)
    ingresos_total = db.Column(db.Float, default=0.0)
    egresos_total = db.Column(db.Float, default=0.0)
    fondo_final = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='abierta')

class MovimientoCaja(db.Model):
    __tablename__ = 'movimientos_caja'
    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'ingreso' o 'egreso'
    monto = db.Column(db.Float, nullable=False)
    concepto = db.Column(db.String(200), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.now)

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    saldo_pendiente = db.Column(db.Float, default=0.0)
    cuentas = db.relationship('CuentaCobrar', backref='cliente', lazy=True)

class CuentaCobrar(db.Model):
    __tablename__ = 'cuentas_cobrar'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    monto_original = db.Column(db.Float, nullable=False)
    monto_pendiente = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='pendiente')

class Abono(db.Model):
    __tablename__ = 'abonos'
    id = db.Column(db.Integer, primary_key=True)
    cuenta_id = db.Column(db.Integer, db.ForeignKey('cuentas_cobrar.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    nota = db.Column(db.String(200), nullable=True)

class Devolucion(db.Model):
    __tablename__ = 'devoluciones'
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    monto_devuelto = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(200), nullable=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)

class EntradaInventario(db.Model):
    __tablename__ = 'entradas_inventario'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    nota = db.Column(db.String(200), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    producto = db.relationship('Producto', backref='entradas')
