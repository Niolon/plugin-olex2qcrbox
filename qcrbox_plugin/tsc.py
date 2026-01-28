import struct
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from textwrap import wrap
from typing import Dict, List, Tuple, Union

import numpy as np
from iotbx.cif.model import block, loop

def read_tsc_file(path: Path):
    """
    Reads a TSC or TSCB file and returns the corresponding object.
    Parameters
    ----------
    path : Path
        The path to the TSC or TSCB file.

    Returns
    -------
    TSCFile or TSCBFile
    The TSCFile or TSCBFile object representing the file content.

    Raises
    ------
    ValueError
    If the file cannot be read as either TSC or TSCB format.
    """
    path = Path(path)
    if path.suffix == ".tscb":
        try:
            return TSCBFile.from_file(path)
        except Exception as exc:
            try:
                return TSCFile.from_file(path)
            except Exception:
                raise ValueError(f"Cannot read TSCB file: {str(path)}") from exc
    elif path.suffix == ".tsc":
        try:
            return TSCFile.from_file(path)
        except Exception as exc:
            try:
                return TSCBFile.from_file(path)
            except Exception:
                raise ValueError(f"Cannot read TSC file: {str(path)}") from exc


def parse_header(header_str):
    """
    Parses the header section of a TSC file.

    Parameters
    ----------
    header_str : str
        The header section of the TSC file as a string.

    Returns
    -------
    dict
        A dictionary containing the parsed header information.
    """
    if not header_str.strip():
        return {}
    header = {}
    header_split = iter(val.split(":") for val in header_str.strip().split("\n"))

    header_key = None
    header_entry = ""
    for line_split in header_split:
        if len(line_split) == 2 and header_key is not None:
            header[header_key] = header_entry
        if len(line_split) == 2:
            header_key, header_entry = line_split
        elif len(line_split) == 1 and header_key is not None:
            header_entry += "\n" + line_split[0]
        else:
            raise ValueError(f"Malformed header line: {':'.join(line_split)}")
    header[header_key] = header_entry
    return header


def parse_tsc_data_line(line: str) -> Tuple[Tuple[int, int, int], np.ndarray]:
    """
    Parses a line of TSC data.

    Parameters
    ----------
    line : str
        The line of TSC data to parse.

    Returns
    -------
    tuple
        A tuple containing the indices h, k, l and the array of f0j values.
    """

    h_str, k_str, l_str, *f0j_strs = line.split()
    parts = (val.split(",") for val in f0j_strs)
    f0js = np.array([float(real_val) + 1j * float(imag_val) for real_val, imag_val in parts])
    return (int(h_str), int(k_str), int(l_str)), f0js


class TSCBase(ABC):
    def __init__(self):
        self.header = {"TITLE": "generic_tsc", "SYMM": "expanded", "SCATTERERS": ""}
        self.data = {}

    @property
    def scatterers(self) -> List[str]:
        """
        Retrieves scatterers from the TSC file as a list of strings generated
        from the SCATTERERS header entry.

        Returns
        -------
        list
            A list of scatterer names.
        """

        return self.header["SCATTERERS"].strip().split()

    @scatterers.setter
    def scatterers(self, scatterers: Iterable):
        """
        Sets the scatterers in the TSC file.

        The input scatterers are converted to a space-separated string and
        stored in the header under the key 'SCATTERERS'.

        Parameters
        ----------
        scatterers : iterable
            An iterable of scatterer names.
        """
        self.header["SCATTERERS"] = " ".join(str(val) for val in scatterers)

    def __getitem__(self, atom_site_label: Union[str, Iterable]) -> Dict[Tuple[int, int, int], np.ndarray]:
        """
        Retrieves f0j values for a given atom site label.

        The function allows indexing the TSCFile object by atom site label or a
        list of labels. If the given label is not found among the scatterers,
        a ValueError is raised.

        Parameters
        ----------
        atom_site_label : str or iterable
            The atom site label or a list of labels to retrieve f0j values for.

        Returns
        -------
        dict
            A dictionary where each key is a tuple of indices (h, k, l) and the
            corresponding value is a numpy array of f0j values for the given
            label(s).

        Raises
        ------
        ValueError
            If an unknown atom site label is used for indexing.
        """
        try:
            if isinstance(atom_site_label, Iterable) and not isinstance(atom_site_label, str):
                indexes = np.array([self.scatterers.index(label) for label in atom_site_label])
                return {hkl: f0js[indexes] for hkl, f0js in self.data.items()}
            else:
                index = self.scatterers.index(atom_site_label)
                return {hkl: f0js[index] for hkl, f0js in self.data.items()}
        except ValueError as exc:
            if isinstance(atom_site_label, Iterable) and not isinstance(atom_site_label, str):
                unknown = [label for label in atom_site_label if label not in self.scatterers]
            else:
                unknown = [atom_site_label]
            raise ValueError(f"Unknown atom label(s) used for lookup from TSCFile: {' '.join(unknown)}") from exc

    @classmethod
    @abstractmethod
    def from_file(cls, filename: Path):
        pass

    @abstractmethod
    def to_file(self, filename: Path):
        pass


    def populate_from_cif_block(self, cif_block: block):
        """
        Populates the TSCFile object from a CIF block created by the TSC to cif export function.
        Parameters
        ----------
        cif_block : block
            The CIF block containing the TSC data.
        Raises
        ------
        ValueError
            If the CIF block does not contain the required entries.
        """
        if (
            "_aspheric_ffs.source" not in cif_block
            or "_aspheric_ffs_partitioning.name" not in cif_block
            or "_aspheric_ffs_partitioning.software" not in cif_block
        ):
            raise ValueError("CIF block does not contain required TSC entries.")
        self.scatterers = cif_block["_wfn_moiety.asu_atom_site_label"]
        aff_loop = cif_block.get_loop("_aspheric_ff")
        if aff_loop is None:
            raise ValueError("CIF block does not contain required TSC entries for the loop _aspheric_ff.")
        hkl_zip = zip(
            aff_loop["_aspheric_ff.index_h"], aff_loop["_aspheric_ff.index_k"], aff_loop["_aspheric_ff.index_l"]
        )
        hkl_tuples = tuple((int(mil_h), int(mil_k), int(mil_l)) for mil_h, mil_k, mil_l in hkl_zip)
        real_lines = aff_loop["_aspheric_ff.form_factor_real"]
        imag_lines = aff_loop["_aspheric_ff.form_factor_imag"]
        real_vals = np.fromiter(
            (float(val) for line in real_lines for val in line.strip("[]").split()), dtype=np.float64
        )
        imag_vals = np.fromiter(
            (float(val) for line in imag_lines for val in line.strip("[]").split()), dtype=np.float64
        )
        all_affs = real_vals + 1j * imag_vals
        n_atoms = len(self.scatterers)
        if len(all_affs) % n_atoms != 0:
            raise ValueError("Number of AFF values is not a multiple of number of scatterers.")
        all_affs = all_affs.reshape((-1, n_atoms))
        if len(hkl_tuples) != len(all_affs):
            raise ValueError("Number of Miller indices does not match number of AFF value sets.")
        self.data = {hkl: affs for hkl, affs in zip(hkl_tuples, all_affs)}

class TSCBFile(TSCBase):
    """
    A class representing a TSCB file used by for example NoSpherA2

    A TSC file contains atomic form factors for a list of atoms and miller
    indicees

    You can get data for atoms for example with tsc['C1'] or tsc[['C1', 'C2']]
    currently setting is not implemented this way. All data is represented
    in the data attribute

    Attributes
    ----------
    header : dict
        A dictionary holding the header information from the TSC file.
    data : dict
        A dictionary mapping tuples (h, k, l) to numpy arrays of f0j values,
        where the ordering of the values is given by the content of the
        scatterers property / the SCATTERERS entry in the header.
    """

    @classmethod
    def from_file(cls, filename: Path) -> "TSCBFile":
        """
        Constructs a TSCFile object from a file.

        The function reads the TSC file, parses its header and data sections,
        and constructs a TSCFile instance with these data.

        Parameters
        ----------
        filename : Path
            The name of the TSC file to read.

        Returns
        -------
        TSCFile
            A TSCBFile instance with data loaded from the file.
        """
        new_obj = cls()
        with open(filename, "rb") as fobj:
            additional_header_size, n_bytes_labels = struct.unpack("2i", fobj.read(8))
            if additional_header_size > 0:
                header_str = fobj.read(additional_header_size).decode("ASCII")

                new_obj.header.update(parse_header(header_str))
            new_obj.header["SCATTERERS"] = fobj.read(n_bytes_labels).decode("ASCII")

            n_refln = struct.unpack("i", fobj.read(4))[0]
            n_atoms = len(new_obj.header["SCATTERERS"].split())
            new_obj.data = {
                tuple(np.frombuffer(fobj.read(12), dtype=np.int32)): np.frombuffer(
                    fobj.read(n_atoms * 16), dtype=np.complex128
                )
                for i in range(n_refln)
            }
        return new_obj

    def to_file(self, filename: Path) -> None:
        """
        Writes the TSCBFile object to a file.

        The function formats the header and data sections of the TSCBFile object
        and writes them to a file. Currently no safety checks are implemented
        SCATTERERS and data need to match

        Parameters
        ----------
        filename : str
            The name of the file to write.
        """
        if not next(iter(self.data.values())).dtype == np.complex128:
            self.data = {key: value.astype(np.complex128) for key, value in self.data.items()}
        omitted_header_entries = ("SCATTERERS", "TITLE", "SYMM")
        header_string = "\n".join(
            f"{name}: {entry}" for name, entry in self.header.items() if name not in omitted_header_entries
        )
        with open(filename, "wb") as fobj:
            fobj.write(struct.pack("2i", len(header_string), len(self.header["SCATTERERS"])))
            fobj.write(header_string.encode("ASCII"))
            fobj.write(self.header["SCATTERERS"].encode("ASCII"))
            fobj.write(struct.pack("i", len(self.data)))
            fobj.write(bytes().join(struct.pack("3i", *hkl) + f0js.tobytes() for hkl, f0js in self.data.items()))

    @classmethod
    def from_cif_string(cls, cif_text: Union[str, bytes]) -> "TSCBFile":
        """
        Constructs a TSCBFile object from CIF text/bytes.

        Parameters
        ----------
        cif_text : str or bytes
            The CIF content as text or bytes.

        Returns
        -------
        TSCBFile
            A TSCBFile instance with data loaded from the CIF content.
        """
        from iotbx.cif import reader
        
        if isinstance(cif_text, bytes):
            cif_text = cif_text.decode('utf-8')
        
        cif_model = reader(input_string=cif_text).model()
        # Get the first block
        block_name = list(cif_model.keys())[0]
        cif_block = cif_model[block_name]
        
        new_obj = cls()
        new_obj.populate_from_cif_block(cif_block)
        return new_obj
    
    @classmethod
    def from_cif_file(cls, cif_path: Path) -> "TSCBFile":
        """
        Constructs a TSCBFile object from a CIF file.

        Parameters
        ----------
        cif_path : Path
            The path to the CIF file to read.

        Returns
        -------
        TSCBFile
            A TSCBFile instance with data loaded from the CIF file.
        """
        with open(cif_path, 'r') as f:
            cif_text = f.read()
        return cls.from_cif_string(cif_text)