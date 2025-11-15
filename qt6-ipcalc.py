#!/usr/bin/env python3
"""
PyQt6 IPCalc - GUI similar a Linux ipcalc con visualización gráfica proporcional de subredes.

Características:
- Cálculo básico IP/CIDR (red, broadcast, netmask, wildcard, rango de hosts, número de hosts)
- Subneteo FLSM (por número de subredes, por hosts ou por máscara secundaria)
- Subneteo VLSM
- Táboa de subredes xeradas
- Visualización gráfica proporcional (o tamaño de cada subrede reflexa a súa cantidade de direccións)

Requisitos:
    pip install PyQt6 matplotlib

Execución:
    python qt6_ipcalc.py
"""
import sys
import math
import ipaddress
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QTabWidget, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QSizePolicy, QInputDialog
)
from PyQt6.QtCore import Qt

VERSION="0.7"

def ip_to_binary_str(ip: ipaddress._BaseAddress) -> str:
    if isinstance(ip, ipaddress.IPv4Address):
        return '.'.join(format(int(octet), '08b') for octet in str(ip).split('.'))
    return ip.exploded  # IPv6 fallback


class SubnetGraphCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots(figsize=(8, 1))
        super().__init__(self.fig)
        self.setParent(parent)
        plt.tight_layout()

    def draw_subnets(self, subnets, names=None):
        self.ax.clear()
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        n = len(subnets)
        if n == 0:
            self.ax.text(0.5, 0.5, 'Non hai subredes para amosar', ha='center', va='center')
        else:
            total_ips = sum(s.num_addresses for s in subnets)
            pos = 0
            for i, subnet in enumerate(subnets):
                rel_width = subnet.num_addresses / total_ips
                color = plt.cm.tab20(i % 20)
                self.ax.barh(0.5, rel_width, left=pos, color=color)
                # label = f"{subnet.network_address}/{subnet.prefixlen}"
                label = (names[i] if names and i < len(names) and names[i]
                         else f"{subnet.network_address}/{subnet.prefixlen}")
                # Si o espazo é moi pequeno tentamos non sobreescribir texto
                self.ax.text(pos + rel_width / 2, 0.5, label,
                             ha='center', va='center', fontsize=8, color='white', rotation=0)
                pos += rel_width

        self.draw()


class IPCalcApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPCalc con visualización proporcional (PyQt6)")
        self.setMinimumSize(900, 700)

        # Engadimos barra de estado coa info da versión
        self.statusBar().showMessage(f'Cálculo de redes - IES Isidro Parga Pondal (Versión {VERSION})')

        tabs = QTabWidget()
        tabs.addTab(self.basic_tab_ui(), "Cálculo básico")
        tabs.addTab(self.subnet_tab_ui(), "Subneteo (FLSM)")
        tabs.addTab(self.vlsm_tab_ui(), "VLSM")

        self.setCentralWidget(tabs)

    # ===============================
    # TAB 1 – **BASIC INFO**
    # ===============================
    def basic_tab_ui(self):
        w = QWidget()
        layout = QVBoxLayout()

        form = QHBoxLayout()
        self.basic_input = QLineEdit()
        self.basic_input.setPlaceholderText("Introduce IP/CIDR (ex: 192.168.1.10/24 ou 192.168.1.0/24)")
        form.addWidget(QLabel("IP/CIDR:"))
        form.addWidget(self.basic_input)
        self.basic_calc_btn = QPushButton("Calcular")
        self.basic_calc_btn.clicked.connect(self.do_basic_calc)
        form.addWidget(self.basic_calc_btn)
        layout.addLayout(form)

        self.basic_result = QLabel()
        self.basic_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.basic_result.setWordWrap(True)
        self.basic_result.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12pt;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
                border: 1px solid #dee2e6;
            }
        """)
        layout.addWidget(self.basic_result)

        w.setLayout(layout)
        return w

    def do_basic_calc(self):
        text = self.basic_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Entrada baleira", "Introduce unha IP/CIDR válida.")
            return
        try:
            net = ipaddress.ip_network(text, strict=False)
            netmask = net.netmask
            hostmask = net.hostmask
            broadcast = net.broadcast_address
            network = net.network_address
            prefix = net.prefixlen
            num_addresses = net.num_addresses
            num_hosts = num_addresses - 2 if num_addresses > 2 else (1 if num_addresses == 1 else 0)

            hosts = list(net.hosts()) if num_addresses > 2 else []
            first_host = hosts[0] if hosts else (network if num_addresses == 1 else "-")
            last_host = hosts[-1] if hosts else (network if num_addresses == 1 else "-")

            wildcard = ipaddress.ip_address(int(hostmask))

            # Estilos CSS para o formato
            styles = """
            <style>
                body { 
                    margin: 0; 
                    padding: 0; 
                    font-size: 12pt;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin-bottom: 15px;
                }
                td {
                    padding: 4px 8px;
                    vertical-align: top;
                    border-bottom: 1px solid #f0f0f0;
                }
                .title { 
                    color: #2c3e50;                                 /* Cor gris-azul escuro */
                    font-weight: bold; 
                    white-space: nowrap;
                    min-width: 160px;
                }
                .network { color: #27ae60; font-weight: bold; }     /* Cor verde */
                .mask { color: #e74c3c; font-weight: bold; }        /* Cor vermello */
                .prefix { color: #3c50e7; font-weight: bold; }      /* Cor azul escuro */
                .hostmask { color: #e7a03c; font-weight: bold; }    /* Cor laranxa */
                .host { color: #3498db; } /* Cor azul */
                .binary { 
                    font-family: 'Courier New', monospace; 
                    font-weight: bold;
                    letter-spacing: 0.5px;
                    word-break: break-all;
                    font-size: 11pt;
                }
                .bit-1 { color: #e74c3c; }                          /* Cor vermello */
                .bit-0 { color: #7f8c8d; }                          /* Cor gris */
                .separator { color: #95a5a6; }                      /* Cor gris azulado */
            </style>
            """

            def color_bits(binary_str):
                """Colorea os bits 1 e 0 con diferentes cores"""
                result = []
                for i, char in enumerate(binary_str):
                    if char in '01':
                        result.append(f'<span class="bit-{char}">{char}</span>')
                    else:
                        result.append(f'<span class="separator">{char}</span>')
                return ''.join(result)

            # Poñemos os estilos na info
            info = [styles]

            # Imos amosar a info nunha táboa para poder aliñar columnas
            info.append('<table style="border-collapse: collapse; width: 100%;">')

            # Función auxiliar para crear filas da táboa
            def add_info(title, value, value_class=''):
                value_class = f' class="{value_class}"' if value_class else ''
                return f'<tr><td class="title">{title}:</td><td{value_class}>{value}</td></tr>'

            # Engadir filas de información
            info.append(add_info('Rede', f'<span class="network">{network}/{prefix}</span>'))
            info.append(add_info('Dirección IP', f'<span class="host">{text}</span>'))
            info.append(add_info('Broadcast', f'<span class="network">{broadcast}</span>'))
            info.append(add_info('Máscara', f'<span class="mask">{netmask}</span> <span class="prefix">(/{prefix})</span>'))
            info.append(add_info('Wildcard', f'<span class="hostmask">{wildcard}</span>'))
            info.append(add_info('Direccións totais', f'<b>{num_addresses:,}</b>'.replace(',', '.')))
            info.append(add_info('Hosts utilizables', f'<b>{num_hosts:,}</b>'.replace(',', '.')))
            info.append(add_info('Primeiro host', f'<span class="host">{first_host}</span>'))
            info.append(add_info('Último host', f'<span class="host">{last_host}</span>'))

            # Pechar a táboa principal
            info.append('</table>')

            # Engadir sección de representacións binarias
            info.append('<div style="margin-top: 15px; font-weight: bold;">Representación binaria:</div>')
            info.append('<table style="width: 100%;">')
            info.append(add_info('Máscara', f'<span class="binary">{color_bits(ip_to_binary_str(netmask))}</span>'))
            info.append(add_info('Wildcard', f'<span class="binary">{color_bits(ip_to_binary_str(wildcard))}</span>'))
            info.append(add_info('IP de rede',
                                 f'<span class="binary">{ip_to_binary_str(net.network_address)}</span>'))
            # Obtemos tamén a IP para convertila a formato binario
            ip4int = ipaddress.ip_interface(text)
            info.append(
                add_info('Dirección IP', f'<span class="binary">{ip_to_binary_str(ip4int.ip)}</span>'))
            info.append('</table>')

            # Unir texto info sin saltos de liña adicionais
            self.basic_result.setText(''.join(info))
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Entrada inválida: {e}")

    # ===============================
    # TAB 2 – **FLSM**
    # ===============================
    def subnet_tab_ui(self):
        w = QWidget()
        layout = QVBoxLayout()

        top = QGroupBox("Parámetros de subneteado")
        top_layout = QFormLayout()

        self.base_net_input = QLineEdit()
        self.base_net_input.setPlaceholderText("Rede base (ex: 10.0.0.0/16)")
        top_layout.addRow("Rede base:", self.base_net_input)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Elixir por Nº de subredes", "Elixir por Hosts por subrede",
                                  "Introducir máscara secundaria (/novo_prefixo)"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        top_layout.addRow("Modo: ", self.mode_combo)

        self.subnets_spin = QSpinBox()
        self.subnets_spin.setRange(1, 2**16)
        self.subnets_spin.setValue(1)
        self.subnets_spin.valueChanged.connect(self.clear_table)
        top_layout.addRow("Nº subredes:", self.subnets_spin)

        self.hosts_spin = QSpinBox()
        self.hosts_spin.setRange(1, 2**24)
        self.hosts_spin.setValue(254)
        self.hosts_spin.valueChanged.connect(self.clear_table)
        top_layout.addRow("Hosts por subrede:", self.hosts_spin)

        self.new_prefix_spin = QSpinBox()
        self.new_prefix_spin.setRange(1, 128)
        self.new_prefix_spin.setValue(24)
        self.new_prefix_spin.valueChanged.connect(self.clear_table)
        top_layout.addRow("Máscara secundaria (/prefixo):", self.new_prefix_spin)

        top.setLayout(top_layout)
        layout.addWidget(top)

        subnetmask_info = QGroupBox("Máscara de subrede")
        subnetmask_layout = QFormLayout()
        self.lbl_subnetmask = QLabel("00000000.00000000.00000000.00000000")
        self.clear_mask()
        subnetmask_layout.addRow(self.lbl_subnetmask)
        subnetmask_info.setLayout(subnetmask_layout)
        layout.addWidget(subnetmask_info)

        """
        btn_layout = QHBoxLayout()
        self.subnet_calc_btn = QPushButton("Xerar subredes")
        self.subnet_calc_btn.clicked.connect(self.do_subnetting)
        btn_layout.addWidget(self.subnet_calc_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        """
        subnet_calc_btn = QPushButton("Xerar subredes")
        subnet_calc_btn.clicked.connect(self.do_subnetting)
        layout.addWidget(subnet_calc_btn)


        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Subrede", "Prefixo", "Máscara", "Rango hosts", "Broadcast",
                                              "Hosts utilizables"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.graph = SubnetGraphCanvas()
        layout.addWidget(QLabel("Visualización gráfica proporcional de subredes:"))
        layout.addWidget(self.graph)

        w.setLayout(layout)
        self.on_mode_changed(0)
        return w

    def on_mode_changed(self, idx):
        self.clear_table()
        # Amosamos ou ocultamos as opcións segundo a opción seleccionada no combo (idx)
        self.subnets_spin.setVisible(idx == 0)
        self.hosts_spin.setVisible(idx == 1)
        self.new_prefix_spin.setVisible(idx == 2)

    def clear_mask(self):
        self.lbl_subnetmask.setText("00000000.00000000.00000000.00000000")
        font = self.lbl_subnetmask.font()
        font.setPointSize(14)
        self.lbl_subnetmask.setFont(font)
        self.lbl_subnetmask.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lbl_subnetmask.setStyleSheet("color: #c0c0c0;") # Cor gris

    def clear_table(self):
        self.clear_mask()
        self.table.setRowCount(0)

    def add_row(self, rowdata):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, text in enumerate(rowdata):
            itm = QTableWidgetItem(str(text))
            itm.setFlags(itm.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, itm)

    def do_subnetting(self):
        # Preparamos o estilo da cadea de máscara de subrede
        styles = """
         <style>
             .binary { 
                 font-family: 'Courier New', monospace; 
                 font-weight: bold;
                 letter-spacing: 0.5px;
                 word-break: break-all;
                 font-size: 14pt;
             }
             .bit-1 { color: #e74c3c; }     /* Cor vermello */
             .bit-1s { color: #732f94; }    /* Cor violeta */
             .bit-0 { color: #7f8c8d; }     /* Cor gris */
             .separator { color: #95a5a6; } /* Cor gris azulado */
         </style>
         """

        def color_bits_submask(binary_str, original_mask_size):
            """Colorea os bits 1 e 0 con diferentes cores, realzando os bits de subrede"""
            result = []
            pos = 1
            for i, char in enumerate(binary_str):
                if char in '01':
                    if char == '1':
                        if pos > original_mask_size:
                            result.append(f'<span class="bit-1s">{char}</span>')
                        else:
                            result.append(f'<span class="bit-1">{char}</span>')
                    else:
                        result.append(f'<span class="bit-0">{char}</span>')
                    pos += 1
                else:
                    result.append(f'<span class="separator">{char}</span>')
            return ''.join(result)


        text = self.base_net_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Entrada baleira", "Introduce unha rede base válida (ex: 192.168.0.0/24)")
            return
        try:
            base = ipaddress.ip_network(text, strict=False)
            original_prefix = base.prefixlen
            mode = self.mode_combo.currentIndex()

            if mode == 0:
                n_subnets = self.subnets_spin.value()
                add_bits = math.ceil(math.log2(n_subnets))
                new_prefix = original_prefix + add_bits
            elif mode == 1:
                hosts = self.hosts_spin.value()
                bits_for_hosts = math.ceil(math.log2(hosts + 2))
                new_prefix = 32 - bits_for_hosts
            else:
                new_prefix = self.new_prefix_spin.value()

            if new_prefix < original_prefix:
                QMessageBox.critical(self, "Error", f"A nova máscara /{new_prefix} "
                                                    f"é menor que a máscara base /{original_prefix}.")
                return

            available_subnets = list(base.subnets(new_prefix=new_prefix))

            self.clear_table()
            subnet_mask = ip_to_binary_str(available_subnets[0].netmask) if available_subnets else ""
            self.lbl_subnetmask.setText(f'<span class="binary">'
                                        f'{styles + color_bits_submask(subnet_mask, original_prefix)}</span>')
            for s in available_subnets:
                netaddr = s.network_address
                prefix = s.prefixlen
                netmask = s.netmask
                broadcast = s.broadcast_address
                total = s.num_addresses
                usable = total - 2 if total > 2 else (1 if total == 1 else 0)
                hosts = list(s.hosts()) if total > 2 else []
                first = hosts[0] if hosts else (netaddr if total == 1 else "-")
                last = hosts[-1] if hosts else (netaddr if total == 1 else "-")
                rng = f"{first} - {last}" if first != "-" else "-"
                self.add_row([f"{s.network_address}/{prefix}", f"/{prefix}", f"{netmask}", rng, str(broadcast),
                              str(usable)])

            # Visualización proporcional
            self.graph.draw_subnets(available_subnets[:20])

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Entrada inválida: {e}")

    # ===============================
    # TAB 3 – **VLSM**
    # ===============================
    def vlsm_tab_ui(self):
        w = QWidget()
        layout = QVBoxLayout()

        # --- Rede base
        box = QGroupBox("Rede base para VLSM")
        form = QFormLayout()
        self.vlsm_base_input = QLineEdit()
        self.vlsm_base_input.setPlaceholderText("Ex: 10.0.0.0/16")
        form.addRow("Rede base:", self.vlsm_base_input)
        box.setLayout(form)
        layout.addWidget(box)

        # --- Lista dinámica de subredes
        self.vlsm_entries = []
        self.entry_names = []
        self.vlsm_subnet_container = QVBoxLayout()

        add_btn = QPushButton("Engadir subrede")
        add_btn.clicked.connect(self.vlsm_add_subnet)
        del_btn = QPushButton("Eliminar última subrede")
        del_btn.clicked.connect(self.vlsm_del_subnet)

        addline = QHBoxLayout()
        addline.addWidget(add_btn)
        addline.addWidget(del_btn)
        layout.addLayout(addline)

        layout.addLayout(self.vlsm_subnet_container)

        # --- Botón calcular
        vlsm_calc_btn = QPushButton("Calcular VLSM")
        vlsm_calc_btn.clicked.connect(self.do_vlsm)
        layout.addWidget(vlsm_calc_btn)

        # --- Táboa saída
        self.vlsm_table = QTableWidget(0, 7)
        self.vlsm_table.setHorizontalHeaderLabels(["Nome", "Subrede", "Prefixo", "Máscara", "Rango hosts", "Broadcast",
                                              "Hosts utilizables"])
        self.vlsm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.vlsm_table)

        # --- Gráfico VLSM
        self.vlsm_graph = SubnetGraphCanvas()
        layout.addWidget(QLabel("Visualización gráfica VLSM (tamaños proporcionales):"))
        layout.addWidget(self.vlsm_graph)

        w.setLayout(layout)
        return w

    def vlsm_add_subnet(self):
        """
        # Solicitamos un nome para a subrede (para amosar logo na gráfica)
        subnet_name, ok = QInputDialog.getText(
            self,
            'Nome da subrede',
            f'Introduce un nome para a subrede {len(self.vlsm_entries) + 1}:'
        )
        if not ok or not subnet_name.strip():
            subnet_name = None
        self.entry_names.append(subnet_name)
        """
        row = QHBoxLayout()
        self.entry_names.append(f'Subrede {len(self.vlsm_entries)+1}')
        label = QLabel(f'Subrede {len(self.vlsm_entries)+1} - Hosts:')
        spin = QSpinBox(); spin.setRange(1, 2**24); spin.setValue(100)
        row.addWidget(label); row.addWidget(spin); row.addStretch()
        self.vlsm_subnet_container.addLayout(row)
        self.vlsm_entries.append((label, spin, row))

    def vlsm_del_subnet(self):
        if not self.vlsm_entries:
            return
        label, spin, row = self.vlsm_entries.pop()
        for i in reversed(range(row.count())):
            widget = row.itemAt(i).widget()
            if widget: widget.deleteLater()
        # Mantemos o Layout aínda que estea baleiro; máis simple

    def do_vlsm(self):
        # 1. Parse base network
        try:
            base = ipaddress.ip_network(self.vlsm_base_input.text().strip(), strict=False)
        except:
            QMessageBox.warning(self, "Erro", "Rede base inválida.")
            return

        # 2. Obteer lista de subredes con hosts
        if not self.vlsm_entries:
            QMessageBox.warning(self, "Erro", "Engade polo menos unha subrede.")
            return

        requests = []
        for _, spin, _ in self.vlsm_entries:
            hosts_needed = spin.value()
            bits = math.ceil(math.log2(hosts_needed + 2))
            prefix = 32 - bits
            requests.append((hosts_needed, prefix))

        # 3. Ordenar de maior a menor
        # requests.sort(reverse=True)
        # Realmente ordeamos as entradas de número de hosts, pero en paralelo aplicamos a mesma orde a entry_names
        combined = list(zip(requests, self.entry_names))
        combined.sort(reverse=True, key=lambda x: x[0])  # Ordena polo primeiro elemento (requests)
        requests, self.entry_names = zip(*combined) if combined else ([], [])
        requests = list(requests)  # Convertimos de novo a lista
        self.entry_names = list(self.entry_names)  # Convertir de novo a lista

        # 4. Asignar subredes consecutivas
        current = int(base.network_address)
        max_addr = current + base.num_addresses

        results = []
        for hosts_needed, prefix in requests:
            size = 2 ** (32 - prefix)
            aligned = (current + (size - 1)) & ~(size - 1)
            if aligned + size > max_addr:
                QMessageBox.critical(self, "Erro", "As subredes non caben na rede base.")
                return
            net = ipaddress.ip_network((aligned, prefix))
            results.append(net)
            current = aligned + size

        # 5. Amosar resultados na táboa
        self.vlsm_table.setRowCount(0)
        for i, s in enumerate(results):
            subnet_name = self.entry_names[i]
            total = s.num_addresses
            usable = total - 2 if total > 2 else 0
            hosts = list(s.hosts()) if usable > 0 else []
            rng = f'{hosts[0]} - {hosts[-1]}' if hosts else "-"
            row = [f'{subnet_name}',
                   f'{s}', f'/{s.prefixlen}', str(s.netmask), rng, str(s.broadcast_address), str(usable)]
            r = self.vlsm_table.rowCount()
            self.vlsm_table.insertRow(r)
            for c, v in enumerate(row): self.vlsm_table.setItem(r, c, QTableWidgetItem(v))

        # 6. Debuxar gráfico VLSM
        self.vlsm_graph.draw_subnets(results,names=self.entry_names)

def main():
    app = QApplication(sys.argv)
    win = IPCalcApp()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
