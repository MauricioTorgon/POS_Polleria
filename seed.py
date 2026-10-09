def seed_products(db, Producto):
    """Inserta productos iniciales si la tabla está vacía."""
    if not Producto.query.first():
        productos_iniciales = [
            Producto(codigo_barras='001', nombre='Pechuga', precio=120.00, unidad_medida='Kg'),
            Producto(codigo_barras='002', nombre='Muslo', precio=95.00, unidad_medida='Kg'),
            Producto(codigo_barras='003', nombre='Pierna', precio=85.00, unidad_medida='Kg')
        ]
        db.session.bulk_save_objects(productos_iniciales)
        db.session.commit()
