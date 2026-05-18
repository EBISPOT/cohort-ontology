## Customize Makefile settings for coho
## 
## If you need to customize your Makefile, make
## changes here rather than in the main Makefile

# Override component template rules to add the COHO prefix mapping,
# which ROBOT needs to resolve COHO:XXXXXXX CURIEs in the CSV templates.
COHO_PREFIX = --prefix "COHO: http://www.ebi.ac.uk/coho/COHO_" \
	--prefix "dbpedia: http://dbpedia.org/resource/" \
	--prefix "oio: http://www.geneontology.org/formats/oboInOwl\#"

ifeq ($(COMP),true)

$(COMPONENTSDIR)/GWAS.owl: $(TEMPLATEDIR)/GWAS.csv $(TMPDIR)/stamp-component-GWAS.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/GWAS.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/MetaboLight.owl: $(TEMPLATEDIR)/MetaboLight.csv $(TMPDIR)/stamp-component-MetaboLight.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/MetaboLight.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/EGA.owl: $(TEMPLATEDIR)/EGA.csv $(TMPDIR)/stamp-component-EGA.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/EGA.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/PRIDE.owl: $(TEMPLATEDIR)/PRIDE.csv $(TMPDIR)/stamp-component-PRIDE.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/PRIDE.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/gaz_xrefs.owl: $(TEMPLATEDIR)/gaz_xrefs.tsv $(TMPDIR)/stamp-component-gaz_xrefs.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/gaz_xrefs.tsv \
		$(ANNOTATE_CONVERT_FILE)
	@# ROBOT emits BFO:0000050 as data property syntax in this template; normalize to object property for OWL 2 DL.
	sed -i.bak 's#DataSomeValuesFrom(<http://purl.obolibrary.org/obo/BFO_0000050>#ObjectSomeValuesFrom(<http://purl.obolibrary.org/obo/BFO_0000050>#g' $(COMPONENTSDIR)/gaz_xrefs.owl
	sed -i.bak 's#Declaration(DataProperty(<http://purl.obolibrary.org/obo/BFO_0000050>))#Declaration(ObjectProperty(<http://purl.obolibrary.org/obo/BFO_0000050>))#g' $(COMPONENTSDIR)/gaz_xrefs.owl
	rm -f $(COMPONENTSDIR)/gaz_xrefs.owl.bak

endif # COMP=true
